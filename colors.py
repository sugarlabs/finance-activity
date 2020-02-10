import logging

CREDIT_COLOR = '#009900'

DEBIT_COLOR = '#ff4040'

CATEGORY_COLORS = [
    (1.0, 1.0, 1.0),
    (1.0, 1.0, 0.6),
    (1.0, 1.0, 0.8),
    (1.0, 0.6, 1.0),
    (1.0, 0.6, 0.6),
    (1.0, 0.6, 0.8),
    (1.0, 0.8, 1.0),
    (1.0, 0.8, 0.6),
    (1.0, 0.8, 0.8),
    (0.6, 1.0, 1.0),
    (0.6, 1.0, 0.6),
    (0.6, 1.0, 0.8),
    (0.6, 0.6, 1.0),
    (0.6, 0.6, 0.6),
    (0.6, 0.6, 0.8),
    (0.6, 0.8, 1.0),
    (0.6, 0.8, 0.6),
    (0.6, 0.8, 0.8),
    (0.8, 1.0, 1.0),
    (0.8, 1.0, 0.6),
    (0.8, 1.0, 0.8),
    (0.8, 0.6, 1.0),
    (0.8, 0.6, 0.6),
    (0.8, 0.6, 0.8),
    (0.8, 0.8, 1.0),
    (0.8, 0.8, 0.6),
    (0.8, 0.8, 0.8),
]


def get_category_color(catname):
    return CATEGORY_COLORS[catname.__hash__() % len(CATEGORY_COLORS)]


def get_category_color_str(catname):
    color = get_category_color(catname)
    return "#%02x%02x%02x" % \
        (int(color[0] * 255), int(color[1] * 255), int(color[2] * 255))


def is_too_light(color):
    return _luminance(color) > 96


def _luminance(color):
    ''' Calculate luminance value '''
    return int(color[1:3], 16) * 0.3 + int(color[3:5], 16) * 0.6 + \
        int(color[5:7], 16) * 0.1


def test_luminances():
    for cat_color in CATEGORY_COLORS:
        color = "#%02x%02x%02x" % \
            (int(cat_color[0] * 255), int(cat_color[1] * 255),
             int(cat_color[2] * 255))
        logging.debug('color %s luminance %s', color, _luminance(color))
