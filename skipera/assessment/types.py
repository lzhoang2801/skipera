# webpack:///static/__generated__/graphql-types.ts
from pydantic import BaseModel
from typing import List, Optional, Any, Literal, get_origin, get_args, Union

WHITELISTED_QUESTION_TYPES = [
    "Submission_CheckboxQuestion",
    "Submission_MultipleChoiceQuestion",
    "Submission_TextReflectQuestion",
    "Submission_RichTextQuestion",
    "Submission_NumericQuestion",
    "Submission_RegexQuestion",
    "Submission_TextExactMatchQuestion",
    "Submission_PlainTextQuestion",
    "Submission_MathQuestion",
    "Submission_WidgetQuestion"
]


QUESTION_TYPE_MAP = {
    "Submission_CheckboxQuestion": ["checkboxResponse", "CHECKBOX"],
    "Submission_CheckboxReflectQuestion": ["checkboxReflectResponse", "CHECKBOX_REFLECT"],
    "Submission_CodeExpressionQuestion": ["codeExpressionResponse", "CODE_EXPRESSION"],
    "Submission_FileUploadQuestion": ["fileUploadResponse", "FILE_UPLOAD"],
    "Submission_MathQuestion": ["mathResponse", "MATH"],
    "Submission_MultipleChoiceQuestion": ["multipleChoiceResponse", "MULTIPLE_CHOICE"],
    "Submission_MultipleChoiceReflectQuestion": ["multipleChoiceReflectResponse", "MULTIPLE_CHOICE_REFLECT"],
    "Submission_MultipleFillableBlanksQuestion": ["multipleFillableBlanksResponse", "MULTIPLE_FILLABLE_BLANKS"],
    "Submission_NumericQuestion": ["numericResponse", "NUMERIC"],
    "Submission_OffPlatformQuestion": ["offPlatformResponse", "PLAIN_TEXT"],
    "Submission_PlainTextQuestion": ["plainTextResponse", "PLAIN_TEXT"],
    "Submission_RegexQuestion": ["regexResponse", "REGEX"],
    "Submission_RichTextQuestion": ["richTextResponse", "RICH_TEXT"],
    "Submission_TextExactMatchQuestion": ["textExactMatchResponse", "TEXT_EXACT_MATCH"],
    "Submission_TextReflectQuestion": ["textReflectResponse", "TEXT_REFLECT"],
    "Submission_UrlQuestion": ["urlResponse", "URL"],
    "Submission_WidgetQuestion": ["widgetResponse", "WIDGET"],
}


class Submission_CodeInput(BaseModel):
    code: Optional[str] = None


class Submission_CheckboxQuestion(BaseModel):
    chosen: Optional[List[str]] = None


class Submission_CodeExpressionQuestion(BaseModel):
    answer: Optional[Submission_CodeInput] = None


class Submission_FileUploadQuestion(BaseModel):
    caption: Optional[str] = None
    fileUrl: Optional[str] = None
    title: Optional[str] = None


class Submission_MathQuestion(BaseModel):
    answer: Optional[str] = None


class Submission_MultipleChoiceQuestion(BaseModel):
    chosen: Optional[str] = None


class Submission_MultipleChoiceFillableBlank(BaseModel):
    id: Optional[str] = None
    optionId: Optional[str] = None


class Submission_FillableBlank(BaseModel):
    multipleChoiceFillableBlankResponse: Optional[Submission_MultipleChoiceFillableBlank] = None


class Submission_MultipleFillableBlanksQuestion(BaseModel):
    responses: Optional[List[Submission_FillableBlank]] = None


class Submission_NumericQuestion(BaseModel):
    answer: Literal[""]  # :(


class Submission_PlainTextQuestion(BaseModel):
    plainText: Optional[str] = None


class Submission_RegexQuestion(BaseModel):
    answer: Optional[str] = None


class Submission_HtmlContentInput(BaseModel):
    value: Optional[str] = None


class Submission_RichTextInput(BaseModel):
    html: Optional[Submission_HtmlContentInput] = None


class Submission_RichTextQuestion(BaseModel):
    richText: Optional[Submission_RichTextInput] = None


class Submission_TextExactMatchQuestion(BaseModel):
    answer: Optional[str] = None


class Submission_TextReflectQuestion(BaseModel):
    answer: Optional[str] = None


class Submission_UrlQuestion(BaseModel):
    caption: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None


class Submission_WidgetQuestion(BaseModel):
    answer: Optional[Any] = None


MODEL_MAP = {
    "Submission_CheckboxQuestion": Submission_CheckboxQuestion,
    "Submission_CodeExpressionQuestion": Submission_CodeExpressionQuestion,
    "Submission_FileUploadQuestion": Submission_FileUploadQuestion,
    "Submission_MathQuestion": Submission_MathQuestion,
    "Submission_MultipleChoiceQuestion": Submission_MultipleChoiceQuestion,
    "Submission_MultipleFillableBlanksQuestion": Submission_MultipleFillableBlanksQuestion,
    "Submission_NumericQuestion": Submission_NumericQuestion,
    "Submission_PlainTextQuestion": Submission_PlainTextQuestion,
    "Submission_RegexQuestion": Submission_RegexQuestion,
    "Submission_RichTextQuestion": Submission_RichTextQuestion,
    "Submission_TextExactMatchQuestion": Submission_TextExactMatchQuestion,
    "Submission_TextReflectQuestion": Submission_TextReflectQuestion,
    "Submission_UrlQuestion": Submission_UrlQuestion,
    "Submission_WidgetQuestion": Submission_WidgetQuestion,
}


def deep_blank_model(model_cls):
    data = {}
    for name, field in model_cls.model_fields.items():
        annotation = field.annotation
        origin = get_origin(annotation)

        if origin is Literal:
            literal_values = get_args(annotation)
            data[name] = literal_values[0]
            continue

        target_type = annotation
        if origin is Union:
            args = [a for a in get_args(annotation) if a is not type(None)]
            if args:
                target_type = args[0]

        if isinstance(target_type, type) and issubclass(target_type, BaseModel):
            data[name] = deep_blank_model(target_type)
        elif target_type is str:
            data[name] = ""
        elif get_origin(target_type) is list or target_type is list:
            data[name] = []
        elif target_type is Any or target_type is dict or get_origin(target_type) is dict:
            data[name] = {}
        else:
            data[name] = None

    return data
