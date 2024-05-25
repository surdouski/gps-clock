from .micro_i2c import MicroPythonI2C
import machine
class GPS(object):
    MAX_I2C_BUFFER = 32
    MAX_GPS_BUFFER = 255

    gnss_messages = {
        'Time'           : 0,
        'Latitude'       : 0,
        'Lat'            : 0,
        'Lat_Direction'  : "",
        'Longitude'      : 0,
        'Long'           : 0,
        'Long_Direction' : "",
        'Altitude'       : 0,
        'Altitude_Units' : "",
        'Sat_Number'     : 0,
        'Geo_Separation' : 0,
        'Geo_Sep_Units'  : "",
    }


    def __init__(self):
        self._i2c = MicroPythonI2C()
        self.address = 0x10  # same as address at i2c.scan()[0]


    def get_raw_data(self):
        raw_sentences = ""
        buffer_tracker = self.MAX_GPS_BUFFER
        raw_data = []
        while buffer_tracker != 0:
            if buffer_tracker > self.MAX_I2C_BUFFER:
                raw_data += self._i2c.readBlock(self.address, 0x00, self.MAX_I2C_BUFFER)
                buffer_tracker = buffer_tracker - self.MAX_I2C_BUFFER
                if raw_data[0] == 0x0A:
                    break
            elif buffer_tracker < self.MAX_I2C_BUFFER:
                raw_data += self._i2c.readBlock(self.address, 0x00, buffer_tracker)
                buffer_tracker = 0
                if raw_data[0] == 0x0A:
                    break
            for raw_bytes in raw_data:
                raw_sentences = raw_sentences + chr(raw_bytes)
        return raw_sentences
    def prepare_data(self):
        sentences = self.get_raw_data()
        clean_gnss_list = []
        complete_sentence_list = []
        gnss_list = sentences.split('\n')
        for sentence in gnss_list:
            if sentence is not '':
                clean_gnss_list.append(sentence)
        for index,sentence in enumerate(clean_gnss_list):
            if not sentence.startswith('$') and index is not 0:
                joined = clean_gnss_list[index - 1] + sentence
                complete_sentence_list.append(joined)
            else:
                complete_sentence_list.append(sentence)
        return complete_sentence_list
    def add_to_gnss_messages(self, sentence):
        try:
            self.gnss_messages['Time'] = sentence.timestamp
            self.gnss_messages['Lat_Direction'] = sentence.lat_dir
            self.gnss_messages['Long_Direction'] = sentence.lon_dir
            self.gnss_messages['Latitude'] = sentence.latitude
            self.gnss_messages['Lat'] = sentence.lat
            self.gnss_messages['Longitude'] = sentence.longitude
            self.gnss_messages['Long'] = sentence.lon
            self.gnss_messages['Altitude'] = sentence.altitude
            self.gnss_messages['Altitude_Units'] = sentence.altitude_units
            self.gnss_messages['Sat_Number'] = sentence.num_sats
            self.gnss_messages['Geo_Separation'] = sentence.geo_sep
            self.gnss_messages['Geo_Sep_Units'] = sentence.geo_sep_units
        except KeyError:
            pass
        except AttributeError:
            pass
        return True