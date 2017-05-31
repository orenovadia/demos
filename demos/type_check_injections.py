"""
Type assertion decoration for a function:

  While it is possible, more readable, and probably better to
wrap functions with a wrapper that raises `ValueError`s if one of the arguments
is of an unexpected type.
see https://stackoverflow.com/questions/15299878/how-to-use-python-decorators-to-check-function-arguments
Cons:
 1. it adds a function call to each call of the decorated function.
 2. It misdirects profilers.


  It is possible, by using AST, to inject type assertions / ValueErrors to the code of the function itself.
And so, not adding an additional function call.
Cons of this method:
  1. Ugliness.
  2. Also unclear when debugging.
  3. It modifies the traceback of the function.
     (Is there a way to keep the line numbers without reading / parsing the entire file?)
"""
import ast
import inspect
from ast import parse, fix_missing_locations
from types import FunctionType
from unittest import TestCase


def type_check_injection(*expected_types):
    def add_type_assertion_to_ast(func_node):
        function_arg_names = [f_arg.arg for f_arg in func_node.body[0].args.args]
        original_function_body = func_node.body[0].body
        type_assertions = []
        func_node.body[0].decorator_list.pop()

        for arg_name, expected_type in zip(function_arg_names, expected_types):
            # TODO: create assertion statement ast rather than parsing string
            assert_code = """assert isinstance({arg_name}, {expected_type_name}), \
            "Arg {arg_name} expected type:{expected_type}, received: %r"%type({arg_name})""".format(
                arg_name=arg_name, expected_type=expected_type, expected_type_name=expected_type.__name__)
            assert_node = parse(assert_code, '<string>', 'exec')
            type_assertions.append(assert_node.body[0])
        # type assertions are first in the functions body
        func_node.body[0].body = type_assertions + original_function_body

        fix_missing_locations(func_node)
        ast.increment_lineno(func_node)  # TODO: maintain actual function line numbers (should parse entire file)

    def wrapper(original_function):
        assert isinstance(original_function, FunctionType)
        func_node = ast.parse(inspect.getsource(original_function))  # parse function source code
        add_type_assertion_to_ast(func_node)  # inject assert statements

        frame = inspect.stack()[1]
        file_of_function = inspect.getmodule(frame[0]).__file__

        compiled = compile(func_node, file_of_function, 'exec')  # compile the module AST
        scope = {}  # make an empty namespace
        exec(compiled, scope, scope)  # now scope contains a proper compiled function

        # Now return the original with the modified version
        return scope[func_node.body[0].name]

    return wrapper


@type_check_injection(int, int)
def int_division(a, b):
    print('in int_division')
    return a / b


class TestTypeAssertInjections(TestCase):
    def test_wrapped_function_works(self):
        self.assertEqual(3, int_division(6, 2))

    def test_invalid_input_type_string(self):
        with self.assertRaises(AssertionError):
            int_division(5, '2')

    def test_invalid_input_float(self):
        with self.assertRaises(AssertionError):
            int_division(2.5, 5)
