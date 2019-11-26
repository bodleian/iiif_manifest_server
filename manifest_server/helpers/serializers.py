from typing import Dict, List, Union
import serpy


class ContextDictSerializer(serpy.DictSerializer):
    """
    Used for serializing Solr results. Extends the basic DictSerializer to include a context parameter
    which can be used to pass extra data into the serializer.

    When serializing also filters out any fields with the value of `None`.
    """
    def __init__(self, *args, **kwargs) -> None:
        super(ContextDictSerializer, self).__init__(*args, **kwargs)
        if 'context' in kwargs:
            self.context = kwargs['context']

    def __remove_none(self, d: Dict) -> Dict:
        return {k: v for k, v in d.items() if v is not None}

    def to_value(self, instance: Union[Dict, List]) -> Union[Dict, List]:
        """
        Filters out values that have been serialized to 'None' to prevent
        them from being sent to the browser.

        :param instance: A dictionary, or list of dictionaries, to be serialized
        :return: A dictionary or a list of dictionaries with 'None' values filtered out.
        """
        v = super().to_value(instance)

        if self.many:
            return [self.__remove_none(d) for d in v]

        return self.__remove_none(v)
