from django import template

register = template.Library()

@register.filter
def getattribute(obj, attr):
    return getattr(obj, attr, None)

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, None)


@register.filter
def to_list(value):
    if isinstance(value, list):
        return value
    return [value]
