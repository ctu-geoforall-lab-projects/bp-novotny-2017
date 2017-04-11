import csv

class ReadCSV():
    def __init__(self, csv_file):
        """Read CSV file into table
        """
        with open(csv_file, 'rb') as f:
            # assuming that first line contains column names
            data = csv.reader(f)
            self._data = dict((row[0], row[1]) for row in data)
        
    def value(self, key):
        """Get value from table.

        :param dictionary: dictionary name
        :param key: row of key
        """
        return self._data.get(key, None)
