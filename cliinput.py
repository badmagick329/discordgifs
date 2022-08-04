from typing import List, Tuple, Optional, Union, Callable
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ValidationResult:
    """
    Represents the result of a validation.
    """
    is_valid: bool
    error_message: str

    def __bool__(self):
        return self.is_valid


@dataclass
class InputValidator:
    """
    A data class to store a validator function and an error message.
    """
    validator: Callable
    error_message: str

    def validate(self, input_value: str) -> ValidationResult:
        res = self.validator(input_value)
        if isinstance(res, bool):
            return ValidationResult(is_valid=res, error_message=self.error_message)
        elif isinstance(res, ValidationResult):
            return res
        else:
            raise TypeError("Validator must return bool or ValidationResult")

    @staticmethod
    def validate_date(input_value: str) -> ValidationResult:
        try:
            datetime.strptime(input_value, "%Y-%m-%d")
            return ValidationResult(is_valid=True, error_message="")
        except ValueError:
            return ValidationResult(is_valid=False, error_message="Invalid date format. Please use YYYY-MM-DD.")

    def __call__(self, *args, **kwargs):
        return self.validate(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.__class__.__name__}("
            f"validator={self.validator.__name__}, "
            f"error_message={self.error_message})"
        )


class CLIInput:
    YES = ["y", "yes"]
    NO = ["n", "no"]

    def __init__(self, required: bool = True,
                 validators: List[Callable] = None, binary_response: bool = False,
                 choices: List = None, case_sensitive: bool = False,
                 optional_choices: List = None, prompt_text: str = ""):
        """
        :param required: Whether the input is required.
        :param validators: User input will be validated against this list of functions before it is returned.
        :param binary_response: Whether the input should be a yes or no response. If true, the choices list is ignored.
        :param choices: A list of choices the user is allowed to pick from. Choices are converted to str before
        comparison.
        :param case_sensitive: Whether the input is case sensitive. Quit words and binary responses are always case
        insensitive.
        :param optional_choices: A list of choices the user is allowed to pick from. Choices are converted to str before
        comparison. If a validation check fails but the input is in the choices list, the input is considered valid.
        :param prompt_text: The text to display to the user when prompting for input.
        """
        self.required = required
        self.binary_response = binary_response

        self.choices = choices if choices else list()
        self.optional_choices = optional_choices if optional_choices else list()
        self.choices_str = ""  # show available choices in prompt
        if self.choices:
            self.choices_str = "Valid choices:\n" + (", ".join([str(c) for c in self.choices]))
        if self.optional_choices:
            self.choices_str += "\n" if self.choices_str else ""
            self.choices_str += "Optional choices:\n" + (", ".join([str(c) for c in self.optional_choices]))
        self.str_choices = [str(c) for c in self.choices]  # for comparison
        self.str_optional_choices = [str(c) for c in self.optional_choices]  # for comparison
        self.case_sensitive = case_sensitive

        self._validators = validators if validators else list()
        self.validators = self.prepare_validators()
        self.prompt_text = prompt_text

    def prompt(self, text: str = "") -> Optional[Union[bool, str]]:
        """
        Prompts the user for input. If the input is not valid, the user is prompted again.
        :param text: The text to display to the user.
        :return: The user input. This will be a bool value for binary responses.
        """
        ptext = text if text else self.prompt_text
        if self.binary_response:
            ptext += "(y/n) "

        while True:
            user_input = input(ptext)

            if user_input == "" and not self.required:
                return None

            if user_input in self.str_optional_choices:
                return user_input

            results = [v(user_input) for v in self.validators]
            if all(results):
                if self.binary_response:
                    return user_input.lower() in self.YES
                return  user_input

            for result in results:
                if not result:
                    print(result.error_message)
                    break

    def valid_binary_response(self, user_input: str) -> bool:
        """Checks if the user input is a valid binary response."""
        return user_input.lower() in self.YES or user_input.lower() in self.NO

    def valid_choice(self, user_input: str) -> bool:
        """
        Checks if the user input is preset in the choices list. If the list has not been set,
        the input is considered valid.
        """
        if self.choices is None:
            return True

        if self.case_sensitive:
            return user_input in [str(c) for c in self.choices]
        else:
            choices = [str(c).lower() for c in self.choices]
            return user_input.lower() in choices

    def prepare_validators(self):
        """
        Prepares the validators for use.
        """
        validators = list()
        for v in self._validators:
            if not isinstance(v, InputValidator):
                validators.append(InputValidator(v, "Invalid input."))
            else:
                validators.append(v)

        if self.required:
            validators.append(InputValidator(validator=lambda x: x != "",
                                             error_message="Input is required."))

        if self.binary_response:
            validators.append(InputValidator(validator=self.valid_binary_response,
                                             error_message="Invalid input. Please enter y or n."))
        elif self.choices:
            validators.append(InputValidator(validator=self.valid_choice,
                                             error_message=f"Invalid input. {self.choices_str}"))

        return validators
