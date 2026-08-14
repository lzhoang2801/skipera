import click
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed
from .config import fetch_browser_cookies, CONFIG_FILE, DEFAULT_CONFIG, BASE_URL, HEADERS, COOKIES, GRAPHQL_URL
import json
from loguru import logger
from .assessment.solver import GradedSolver
from .discussion.solver import DiscussionPromptSolver
from .coach.solver import CoachSolver
from .watcher.watch import Watcher
from .session_utils import get_csrf_headers, random_delay


class Skipera(object):
    def __init__(self, course: str, llm: bool):
        self.user_id = None
        self.course_id = None
        self.base_url = BASE_URL
        self.session = httpx.Client(timeout=60.0, follow_redirects=True)
        self.session.headers.update(HEADERS)
        self.session.cookies.update(COOKIES)
        self.course = course
        self.llm = llm
        self.failed_items = set()
        if not self.get_userid():
            self.refresh_cookies()
            if not self.get_userid():
                logger.error(
                    "Cookies are invalid. Log into Coursera in your browser, close it, and retry.")
                raise SystemExit

    def refresh_cookies(self):
        logger.warning("Session expired — re-fetching cookies from browser...")
        cookies = fetch_browser_cookies()
        if not cookies:
            return
        self.session.cookies.clear()
        self.session.cookies.update(cookies)
        cfg = json.loads(CONFIG_FILE.read_text()
                         ) if CONFIG_FILE.exists() else DEFAULT_CONFIG.copy()
        cfg["cookies"] = cookies
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

    def get_userid(self) -> bool:
        r = self.session.get(self.base_url + "adminUserPermissions.v1?q=my")
        if r.status_code == 200:
            data = r.json()
            self.user_id = str(data["elements"][0]["id"])
            logger.info("User ID: " + self.user_id)
            return True
        else:
            data = r.json()
            if data.get("errorCode"):
                logger.error("Error Encountered: " + data["errorCode"])

        return False

    def get_course(self) -> None:
        self.course_id = self.get_course_id()
        num_items, num_modules, _ = self.get_course_items()

        logger.info("Course ID: " + self.course_id)
        logger.info(f"Number of Modules: {num_modules}")
        logger.info(f"Total items: {num_items}")

        self.process_items()

    def get_course_id(self) -> str:
        r = self.session.get(self.base_url + "onDemandCourseMaterials.v2/", params={
            "q": "slug",
            "slug": self.course,
            "fields": "id"
        })

        if r.status_code != 200:
            logger.error("Please check if you are enrolled in the course!")
            raise SystemExit

        return r.json()["elements"][0]["id"]

    def get_course_items(self) -> tuple[int, int, list[dict]]:
        r = self.session.get(
            self.base_url + "guidedCourseSessionProgresses.v1",
            params={
                "ids": f"{self.user_id}~{self.course_id}",
                "fields": "id,startedAt,endedAt,weeks,courseProgressState"
            }
        )

        if r.status_code != 200:
            logger.error("Could not fetch guided course session progress.")
            logger.debug(r.text)
            return 0, 0, []

        elements = r.json().get("elements") or []
        if not elements:
            logger.error("No items found in course.")
            logger.debug(r.text)
            return 0, 0, []

        num_items = 0
        uncompleted_items = []
        num_modules = 0
        weeks = elements[0].get("weeks") or []
        for week in weeks:
            modules = week.get("modules") or []
            num_modules += len(modules)
            for module in modules:
                module_id = module.get("id", "unknown")
                for item in module.get("items") or []:
                    num_items += 1
                    item["moduleId"] = module_id
                    if item.get("computedProgressState") != "Completed":
                        uncompleted_items.append(item)

        return num_items, num_modules, uncompleted_items

    def process_items(self) -> None:
        while True:
            num_items, _, uncompleted_items = self.get_course_items()
            if not uncompleted_items:
                logger.error("No uncompleted items found in course.")
                break

            total = num_items
            unlocked_items = [
                item for item in uncompleted_items
                if not item.get("isLocked", False) and item["id"] not in self.failed_items
            ]
            if not unlocked_items:
                logger.info(
                    f"Finished: {total - len(uncompleted_items)}/{total} completed, {len(uncompleted_items)} still locked/pending."
                )
                break

            concurrent_items = []
            sequential_items = []
            for item in unlocked_items:
                if item["contentSummary"]["typeName"] not in {"discussionPrompt", "ungradedAssignment", "staffGraded", "phasedPeer"}:
                    concurrent_items.append(item)
                else:
                    sequential_items.append(item)

            if concurrent_items:
                with ThreadPoolExecutor(max_workers=min(6, len(concurrent_items))) as executor:
                    futures = {
                        executor.submit(self.process_item, item): item
                        for item in concurrent_items
                    }
                    for future in as_completed(futures):
                        item = futures[future]
                        try:
                            success = future.result()
                            if not success:
                                self.failed_items.add(item["id"])
                        except Exception as e:
                            logger.exception(f"Error in processing item: {e}")
                            self.failed_items.add(item["id"])
                continue

            if sequential_items:
                item = sequential_items[0]
                try:
                    success = self.process_item(item)
                    if not success:
                        self.failed_items.add(item["id"])
                except Exception as e:
                    logger.exception(f"Error in processing item: {e}")
                    self.failed_items.add(item["id"])
                continue

    def process_item(self, item: dict) -> bool:
        item_type = item["contentSummary"]["typeName"]
        module_id = item.get('moduleId', 'unknown')
        item_id = item['id']
        logger.info(
            f"[module:{module_id}] [item:{item_id}] Processing {item['name']}")

        success = False
        if item_type == "lecture":
            success = self.watch_item(item, self.get_video_metadata(item_id))
        elif item_type == "supplement":
            success = self.read_item(item_id)
        elif item_type in {"ungradedAssignment", "staffGraded"} and self.llm:
            success = GradedSolver(
                self.session, self.course_id, item_id).solve()
        elif item_type == "discussionPrompt" and self.llm:
            success = DiscussionPromptSolver(
                self.session, self.user_id, self.course_id, item_id).solve()
        elif item_type == "coach":
            success = CoachSolver(
                self.session, self.user_id, self.course_id, item_id).solve()
        elif item_type == "ungradedWidget":
            success = self.ungraded_widget_item(item_id)
        elif item_type == "ungradedLab":
            success = self.ungraded_lab_item(item_id)
        elif item_type == "ungradedLti":
            success = self.ungraded_lti_item(item_id)
        else:
            logger.warning(
                f"[module:{module_id}] [item:{item_id}] Unknown/skipped item type: {item_type} - skipping.")

        return success

    def get_video_metadata(self, item_id: str) -> dict:
        r = self.session.get(self.base_url + f"onDemandLectureVideos.v1/{self.course_id}~{item_id}", params={
            "includes": "video",
            "fields": "disableSkippingForward,startMs,endMs"
        }).json()

        return {"can_skip": not r["elements"][0]["disableSkippingForward"],
                "tracking_id": r["linked"]["onDemandVideos.v1"][0]["id"]}

    def watch_item(self, item: dict, metadata: dict) -> bool:
        watcher = Watcher(self.session, item, metadata,
                          self.user_id, self.course, self.course_id)
        return watcher.watch_item()

    def read_item(self, item_id) -> bool:
        r = self.session.post(self.base_url + "onDemandSupplementCompletions.v1",
                              headers=get_csrf_headers(self.session),
                              json={
                                  "courseId": self.course_id,
                                  "itemId": item_id,
                                  "userId": int(self.user_id)
                              })
        return "Completed" in r.text

    def ungraded_widget_item(self, item_id) -> bool:
        r = self.session.get(
            self.base_url +
            f"onDemandWidgetSessions.v1/{self.user_id}~{self.course_id}~{item_id}",
            params={"fields": "session,sessionId"}
        )
        if r.status_code != 200:
            logger.error(
                f"Failed to get session for widget {item_id}: {r.status_code}")
            return False

        try:
            session_id = r.json()["elements"][0]["sessionId"]
        except (KeyError, IndexError):
            logger.error(f"Could not parse sessionId for widget {item_id}")
            return False

        res = self.session.put(
            self.base_url +
            f"onDemandWidgetProgress.v1/{self.user_id}~{self.course_id}~{item_id}",
            headers=get_csrf_headers(self.session),
            json={
                "sessionId": session_id,
                "progressState": "Completed"
            }
        )
        return 200 <= res.status_code < 300

    def ungraded_lab_item(self, item_id: str) -> bool:
        headers = get_csrf_headers(self.session)
        headers["operation-name"] = "InLabInstructions_MarkInstructionAsComplete"

        mutation = """
mutation InLabInstructions_MarkInstructionAsComplete($input: InLabInstructions_MarkInstructionAsCompleteInput!) {
  InLabInstructions_MarkInstructionAsComplete(input: $input) {
    completedInstructions {
      instructionId
      __typename
    }
    course {
      id
      __typename
    }
    itemId
    __typename
  }
}
"""
        res = self.session.post(
            GRAPHQL_URL,
            headers=headers,
            params={"opname": "InLabInstructions_MarkInstructionAsComplete"},
            json={
                "operationName": "InLabInstructions_MarkInstructionAsComplete",
                "variables": {
                    "input": {
                        "courseId": self.course_id,
                        "itemId": item_id,
                        "instructionId": "q4AHDS94Ee-PygJCrBEACA"
                    }
                },
                "query": mutation
            }
        )
        if 200 <= res.status_code < 300 and not res.json().get("errors"):
            return True

        return False

    def ungraded_lti_item(self, item_id) -> bool:
        r = self.session.post(
            self.base_url + "rest/v1/lti/ungradedLaunches",
            headers=get_csrf_headers(self.session),
            json={
                "courseId": self.course_id,
                "itemId": item_id,
                "learnerId": int(self.user_id),
                "markItemCompleted": True
            }
        )
        return 200 <= r.status_code < 300


@logger.catch
@click.command()
@click.argument('slug')
@click.option('--llm', is_flag=True, help="Whether to use an LLM to solve graded assignments.")
def main(slug: str, llm: bool) -> None:
    skipera = Skipera(slug, llm)
    skipera.get_course()


if __name__ == '__main__':
    main()
