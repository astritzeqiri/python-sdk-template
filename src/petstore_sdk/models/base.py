import re
from typing import List, Union, get_origin, get_args
from enum import Enum


class BaseModel:
    """
    A base class that most of the models in the SDK inherited from.
    """

    def __init__(self):
        pass

    def _pattern_matching(self, value: str, pattern: str, variable_name: str):
        """
        Checks if a value matches a regex pattern and returns the value if there's a match.

        :param value: The value to be checked.
        :type value: str
        :param pattern: The regex pattern.
        :type pattern: str
        :param variable_name: The variable name.
        :type variable_name: str
        :return: The value if it matches the pattern.
        :rtype: str
        :raises ValueError: If the value does not match the pattern.
        """
        if value is None:
            return None

        if re.match(r"{}".format(pattern), value):
            return value
        else:
            raise ValueError(f"Invalid value for {variable_name}: must match {pattern}")

    def _enum_matching(
        self, value: Union[str, Enum], enum_values: List[str], variable_name: str
    ):
        """
        Checks if a value (str or enum) matches the required enum values and returns the value if there's a match.

        :param value: The value to be checked.
        :type value: Union[str, Enum]
        :param enum_values: The list of valid enum values.
        :type enum_values: List[str]
        :param variable_name: The variable name.
        :type variable_name: str
        :return: The value if it matches one of the enum values.
        :rtype: Union[str, Enum]
        :raises ValueError: If the value does not match any of the enum values.
        """
        if value is None:
            return None

        str_value = value.value if isinstance(value, Enum) else value
        if str_value in enum_values:
            return value
        else:
            raise ValueError(
                f"Invalid value for {variable_name}: must match one of {enum_values}"
            )

    def _define_object(self, input_data, input_class):
        """
        Check if the input data is an instance of the input class and return the input data if it is.
        Otherwise, return an instance of the input class.

        :param input_data: The input data to be checked.
        :param input_class: The class that the input data should be an instance of.
        :return: The input data if it is an instance of input_class, otherwise an instance of input_class.
        :rtype: object
        """
        if input_data is None:
            return None
        elif isinstance(input_data, input_class):
            return input_data
        else:
            return input_class._unmap(input_data)

    def _define_list(self, input_data, list_class):
        """
        Create a list of instances of a specified class from input data.

        :param input_data: The input data to be transformed into a list of instances.
        :param list_class: The class that each instance in the list should be an instance of.
        :return: A list of instances of list_class.
        :rtype: list
        """

        if input_data is None:
            return None

        result = []
        for item in input_data:
            if hasattr(list_class, "__args__") and len(list_class.__args__) > 0:
                class_list = self.__create_class_map(list_class)
                OneOfBaseModel.class_list = class_list
                result.append(OneOfBaseModel.return_one_of(item))
            elif issubclass(list_class, Enum):
                result.append(
                    self._enum_matching(item, list_class.list(), list_class.__name__)
                )
            elif isinstance(item, list_class):
                result.append(item)
            elif isinstance(item, dict):
                result.append(list_class._unmap(item))
            else:
                result.append(list_class(item))
        return result

    def __create_class_map(self, union_type):
        """
        Create a dictionary that maps class names to the actual classes in a Union type.

        :param union_type: The Union type to create a class map for.
        :return: A dictionary mapping class names to classes.
        :rtype: dict
        """
        class_map = {}
        for arg in union_type.__args__:
            if arg.__name__:
                class_map[arg.__name__] = arg
        return class_map

    def _get_representation(self, level=0):
        """
        Get a string representation of the model.

        :param int level: The indentation level.
        :return: A string representation of the model.
        """
        indent = "    " * level
        representation_lines = []

        for attr, value in vars(self).items():
            if value is not None:
                value_representation = (
                    value._get_representation(level + 1)
                    if hasattr(value, "_get_representation")
                    else repr(value)
                )
                representation_lines.append(
                    f"{indent}    {attr}={value_representation}"
                )

        return (
            f"{self.__class__.__name__}(\n"
            + ",\n".join(representation_lines)
            + f"\n{indent})"
        )

    def __str__(self):
        return self._get_representation()

    def __repr__(self):
        return self._get_representation()


class OneOfBaseModel:
    """
    A base class for handling 'oneOf' models where multiple class constructors are available,
    and the appropriate one is determined based on the input data.

    :ivar dict class_list: A dictionary mapping class names to their constructors.
    """

    class_list = {}

    @classmethod
    def return_one_of(cls, input_data):
        """
        Attempts to initialize an instance of one of the classes in the class_list
        based on the provided input data.

        :param input_data: Input data used for initialization.
        :return: An instance of one of the classes specified.
        :rtype: object
        :raises ValueError: If no class can be initialized with the provided input data,
            or if optional parameters don't match the input data.
        """
        if input_data is None:
            return None

        if isinstance(input_data, (str, float, int, bool)):
            return input_data

        for class_constructor in cls.class_list.values():
            try:
                # Check if the class is a only a TypeHint
                origin = get_origin(class_constructor)
                if origin is not None and isinstance(input_data, list):
                    list_instance = cls._get_list_instance(
                        input_data, class_constructor, origin
                    )
                    if list_instance is not None:
                        return list_instance
                    else:
                        continue  # Try the next class constructor

                # Check if the input_data is already an instance of the class
                if isinstance(input_data, class_constructor):
                    return input_data

                # Check if the input_data is a dictionary that can be used to initialize the class
                elif isinstance(input_data, dict):
                    instance = class_constructor._unmap(input_data)
                    if cls._check_params(input_data, instance):
                        return instance
            except Exception:
                pass

        raise ValueError(
            f"Input data must match one of the models: {list(cls.class_list.keys())}"
        )

    @classmethod
    def _get_list_instance(cls, input_data, class_constructor, origin):
        """
        Return the list of elements for a given class constructor and origin type.

        :param input_data: The input data to check.
        :param class_constructor: The constructor of the class to check against.
        :param origin: The origin type to check against.
        :return: The input data if all elements are instances of the type specified in the class_constructor,
            or a new list with each item unmapped.
        """
        args = get_args(class_constructor)
        if isinstance(input_data, origin):
            if args and len(args) == 1 and isinstance(input_data, list):
                inner_type = args[0]
                if all(isinstance(item, inner_type) for item in input_data):
                    return input_data
                else:
                    return [inner_type._unmap(item) for item in input_data]

    @classmethod
    def _check_params(cls, raw_input, instance):
        """
        Checks if the optional parameters in the instance match the keys in the input data,
        ensuring compliance with one of the models.

        :param dict raw_input: Input data used for initialization.
        :param object instance: An instance of one of the classes specified in the 'oneOf' model.
        :return: True if the optional parameters in the instance match the keys in the input data, False otherwise.
        """
        input_values = {k: v for k, v in raw_input.items() if v is not None}.values()
        instance_map = instance._map()
        instance_values = {
            k: v for k, v in instance_map.items() if v is not None
        }.values()
        return len(input_values) == len(instance_values)
