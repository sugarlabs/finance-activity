# Copyright 2008 by Wade Brainerd.
# This file is part of Finance.
#
# Finance is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Finance is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Finance.  If not, see <http://www.gnu.org/licenses/>.

# Import standard Python modules.
import math
import locale
import cairo
import logging

# Import activity module
import colors

from gettext import gettext as _

from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import PangoCairo

from sugar3.graphics import style

CHART_HELP = _(
    'The Chart view shows the proportion of your expenses that is in each '
    'category.\nYou can categorize transactions in the Register view.')


def _get_screen_dpi():
    xft_dpi = Gtk.Settings.get_default().get_property('gtk-xft-dpi')
    dpi = float(xft_dpi / 1024)
    logging.debug('Setting dpi to: %f', dpi)
    return dpi


def _set_screen_dpi():
    dpi = _get_screen_dpi()
    font_map_default = PangoCairo.font_map_get_default()
    font_map_default.set_resolution(dpi)


class ChartScreen(Gtk.VBox):

    CHART_CREDIT = 'credit'
    CHART_DEBIT = 'debit'

    def __init__(self, activity):
        GObject.GObject.__init__(self)

        self.activity = activity

        self.category_total = {}
        self.sorted_categories = []
        self._graph_mode = self.CHART_DEBIT

        header = Gtk.EventBox()
        header.modify_bg(Gtk.StateType.NORMAL,
                         style.Color('#666666').get_gdk_color())
        header.set_size_request(-1, style.GRID_CELL_SIZE)

        self._title_label = Gtk.Label()
        self._title_label.set_halign(Gtk.Align.START)
        self._title_label.props.margin_left = style.GRID_CELL_SIZE / 2
        header.add(self._title_label)

        self.area = Gtk.DrawingArea()
        self.area.connect('draw', self.chart_draw_cb)

        self.pack_start(header, False, False, 0)
        self.pack_start(self.area, True, True, 0)

        self.show_all()

    def set_mode(self, mode):
        self._graph_mode = mode
        self.build()

    def build(self):

        if self._graph_mode == self.CHART_CREDIT:
            self.title = _('Credit Categories')
        elif self._graph_mode == self.CHART_DEBIT:
            self.title = _('Debit Categories')

        self._title_label.set_markup(
            '<span size="x-large" foreground="white"><b>%s</b></span>' %
            self.title)

        # Build the category totals.
        self.category_total = {}
        for t in self.activity.visible_transactions:
            cat = t['category']
            amount = t['amount']

            if t['type'] == self._graph_mode:
                if cat not in self.category_total:
                    self.category_total[cat] = amount
                else:
                    self.category_total[cat] += amount

        # Generate a list of names sorted by total.
        self.sorted_categories = list(self.category_total.keys())
        # self.sorted_categories.sort(key = lamba a, b: self.category_total[a])
        self.area.queue_draw()

    def generate_image(self, image_file, width, height):
        image_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)

        context = cairo.Context(image_surface)
        self.create_chart(context, width, height)
        image_surface.flush()
        image_surface.write_to_png(image_file)

    def chart_draw_cb(self, widget, context):
        # Draw pie chart.
        bounds = widget.get_allocation()
        self.create_chart(context, bounds.width, bounds.height)

    def create_chart(self, context, image_width, image_height):

        _set_screen_dpi()

        scale = image_width / 1600.
        context.rectangle(0, 0, image_width, image_height)
        logging.debug('canvas size %s x %s - scale %s', image_width,
                      image_height, scale)
        context.set_source_rgb(1, 1, 1)
        context.fill()

        margin_left = (style.GRID_CELL_SIZE / 2) * scale
        margin_top = (style.GRID_CELL_SIZE / 2) * scale
        padding = 20 * scale

        # measure the descriptions
        max_width_desc = 0
        max_width_amount = 0
        max_height = 0
        context.select_font_face('Sans', cairo.FONT_SLANT_NORMAL,
                                 cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(26 * scale)

        for c in self.sorted_categories:
            description = c
            # If there is no category, display as Unknown
            if c == '':
                description = _('Unknown')

            # need measure the description width to align the amounts
            x_bearing, y_bearing, width, height, x_advance, y_advance = \
                context.text_extents(description)
            max_width_desc = max(max_width_desc, width)
            max_height = max(max_height, height)

            x_bearing, y_bearing, width, height, x_advance, y_advance = \
                context.text_extents(locale.currency(self.category_total[c]))
            max_height = max(max_height, height)
            max_width_amount = max(max_width_amount, width)

        # draw the labels
        y = margin_top
        context.save()
        context.translate(margin_left, 0)
        rectangles_width = max_width_desc + max_width_amount + padding * 3
        for c in self.sorted_categories:
            description = c
            if c == '':
                description = _('Unknown')
            context.save()
            context.translate(0, y)
            context.rectangle(0, 0, rectangles_width, max_height + padding)

            color = colors.get_category_color(c)
            context.set_source_rgb(color[0], color[1], color[2])
            context.fill()

            if colors.is_too_light(colors.get_category_color_str(c)):
                context.set_source_rgb(0, 0, 0)
            else:
                context.set_source_rgb(1, 1, 1)

            context.save()
            x_bearing, y_bearing, width, height, x_advance, y_advance = \
                context.text_extents(description)
            context.move_to(padding, padding * 2.5 + y_bearing)
            context.show_text(description)
            context.restore()

            context.save()
            text = locale.currency(self.category_total[c])
            x_bearing, y_bearing, width, height, x_advance, y_advance = \
                context.text_extents(text)
            context.move_to(rectangles_width - x_advance - padding,
                            padding * 2.5 + y_bearing)
            context.show_text(text)
            context.restore()

            y += max_height + padding * 2
            context.restore()

        context.restore()

        # draw the pie
        x = (image_width - rectangles_width) / 2 + rectangles_width
        y = image_height / 2
        r = min(image_width, image_height) / 2 - 10

        total = 0
        for c in self.sorted_categories:
            total += self.category_total[c]

        if total != 0:
            angle = 0.0

            for c in self.sorted_categories:
                slice = 2 * math.pi * self.category_total[c] / total
                color = colors.get_category_color(c)

                context.move_to(x, y)
                context.arc(x, y, r, angle, angle + slice)
                context.close_path()

                context.set_source_rgb(color[0], color[1], color[2])
                context.fill()

                midpoint_angle = angle + slice / 2
                midpoint_x = x + (r / 2) * math.cos(midpoint_angle)
                midpoint_y = y + (r / 2) * math.sin(midpoint_angle)

                context.save()
                context.translate(midpoint_x, midpoint_y)
                context.rotate(midpoint_angle + math.pi)
                context.set_font_size(16 * scale)
                context.set_source_rgb(0, 0, 0)
                context.show_text(c)
                context.restore()

                angle += slice
