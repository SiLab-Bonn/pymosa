import numpy as np
from zmq.utils import jsonapi

from online_monitor.converter.transceiver import Transceiver
from online_monitor.utils import utils
from pymosa_mimosa26_interpreter import raw_data_interpreter


class PymosaMimosa26(Transceiver):

    def setup_interpretation(self):
        analyze_m26_header_ids = self.config.get('analyze_m26_header_ids', [1, 2, 3, 4, 5, 6])
        self._raw_data_interpreter = raw_data_interpreter.RawDataInterpreter(analyze_m26_header_ids=analyze_m26_header_ids)
        self.n_hits = 0
        self.n_events = 0

    def deserialize_data(self, data):  # According to pyBAR data serilization
        try:
            self.meta_data = jsonapi.loads(data)
        except ValueError:
            try:
                dtype = self.meta_data.pop('dtype')
                shape = self.meta_data.pop('shape')
                if self.meta_data:
                    try:
                        raw_data_array = np.frombuffer(data, dtype=dtype).reshape(shape)
                        return raw_data_array
                    except (KeyError, ValueError):  # KeyError happens if meta data read is omitted; ValueError if np.frombuffer fails due to wrong shape
                        return None
            except AttributeError:  # Happens if first data is not meta data
                return None
        return {'meta_data': self.meta_data}

    def interpret_data(self, data):
        if isinstance(data[0][1], dict):  # Meta data is omitted, only raw data is interpreted
            # Add info to meta data
            data[0][1]['meta_data'].update({'n_hits': self.n_hits, 'n_events': self.n_events})
            return [data[0][1]]
        hits = self._raw_data_interpreter.interpret_raw_data(raw_data=data[0][1])

        interpreted_data = {
            'hits': hits
        }

        self.n_hits = hits.shape[0]
        self.n_events = np.unique(hits['event_number']).shape[0]

        return [interpreted_data]

    def serialize_data(self, data):
        if 'hits' in data:
            hits_data = data['hits']
            data['hits'] = None
            return utils.simple_enc(hits_data, data)
        else:
            return utils.simple_enc(None, data)
