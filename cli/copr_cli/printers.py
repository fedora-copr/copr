"""
Abstraction for printing data to copr-cli's stdout
"""

from .util import json_dumps


class AbstractPrinter(object):
    """Abstract class defining mandatory methods of printer classes"""

    def __init__(self, fields):
        """Represents the data we want to print.
        Supports callable lambda function which takes exactly one argument"""
        self.fields = fields

    def add_data(self, data):
        """Initialize the data to be printed"""
        raise NotImplementedError

    def finish(self):
        """Print the data according to the set format"""
        raise NotImplementedError


class RowTextPrinter(AbstractPrinter):
    """The class takes care of printing the data in row text format"""

    def finish(self):
        pass

    def add_data(self, data):
        row_data = []
        for field in self.fields:
            if callable(field):
                row_data.append(str(field(data)))
            else:
                row_data.append(str(data[field]))
        print("\t".join(row_data))


class ColumnTextPrinter(AbstractPrinter):
    """The class takes care of printing the data in column text format"""

    first_line = True

    def finish(self):
        pass

    def add_data(self, data):
        if not self.first_line:
            print()
        self.first_line = False
        for field in self.fields:
            if callable(field):
                print("{0}: {1}".format(field.__code__.co_varnames[0], str(field(data))))
            else:
                print("{0}: {1}".format(field, str(data[field])))


class JsonPrinter(AbstractPrinter):
    """The class takes care of printing the data in json format"""

    def _get_result_json(self, data):
        result = {}
        for field in self.fields:
            if callable(field):
                name = field.__code__.co_varnames[0]
                result[name] = field(data)
            else:
                result[field] = data[field]
        return json_dumps(result)

    def add_data(self, data):
        print(self._get_result_json(data))

    def finish(self):
        pass


class JsonPrinterListCommand(JsonPrinter):
    """
    The class takes care of printing the data in list in json format

    For performance reasons we cannot simply add everything to a list and then
    use `json_dumps` function to print all JSON at once. For large projects this
    would mean minutes of no output, which is not user-friendly.

    The approach here is to utilize `json_dumps` to convert each object to
    a JSON string and print it immediately. We then manually take care of
    opening and closing list brackets and separators.
    """

    first_line = True

    def add_data(self, data):
        self.start()
        result = self._get_result_json(data)
        for line in result.split("\n"):
            print("    {0}".format(line))

    def start(self):
        """
        This is called before printing the first object
        """
        if self.first_line:
            self.first_line = False
            print("[")
        else:
            print("    ,")

    def finish(self):
        """
        This is called by the user after printing all objects
        """
        if not self.first_line:
            print("]")


def cli_get_output_printer(output_format, fields, list_command=False):
    """According to output_format decide which object of printer to return"""
    if output_format == "json":
        if list_command:
            return JsonPrinterListCommand(fields)
        return JsonPrinter(fields)
    if output_format == "text":
        return ColumnTextPrinter(fields)
    return RowTextPrinter(fields)
