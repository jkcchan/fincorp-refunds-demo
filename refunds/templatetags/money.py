from django import template

register = template.Library()


@register.filter
def dollars(minor):
    return f"{minor / 100:,.2f}"
