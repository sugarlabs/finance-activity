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

# Import activity module
import colors

from gettext import gettext as _

from gi.repository import Gtk
from gi.repository import GObject

from sugar3.graphics import style

# Set up localization.
locale.setlocale(locale.LC_ALL, '')

CHART_HELP = _(
    'The Chart view shows the proportion of your expenses that is in each '
    'category.\nYou can categorize transactions in the Register view.')


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
            title = _('Credit Categories')
        elif self._graph_mode == self.CHART_DEBIT:
            title = _('Debit Categories')

        self._title_label.set_markup(
            '<span size="x-large" foreground="white"><b>%s</b></span>' %
            title)

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
        self.sorted_categories = self.category_total.keys()
        # self.sorted_categories.sort(lamba a, b: cmp(self.category_total[a],
        #                                             self.category_total[b]))
        self.area.queue_draw()

    def chart_draw_cb(self, widget, context):
        # Draw pie chart.
        bounds = widget.get_allocation()
        context.rectangle(0, 0, bounds.width, bounds.height)
        context.set_source_rgb(1, 1, 1)
        context.fill()

        # draw the labels

        margin_left = style.GRID_CELL_SIZE / 2
        margin_top = style.GRID_CELL_SIZE / 2
        padding = 20

        # measure the descriptions
        max_width_desc = 0
        max_width_amount = 0
        max_height = 0
        context.select_font_face('Sans', cairo.FONT_SLANT_NORMAL,
                                 cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(20)

        for c in self.sorted_categories:
            description = c
            # If there is no category, display as Unknown
            if c is '':
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
            if c is '':
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
            context.move_to(padding, padding * 2 - height)
            context.show_text(description)
            context.restore()

            context.save()
            x_bearing, y_bearing, width, height, x_advance, y_advance = \
                context.text_extents(description)
            context.move_to(max_width_desc + padding * 2,
                            padding * 2 - height)
            context.show_text(locale.currency(self.category_total[c]))
            context.restore()

            y += max_height + padding * 2
            context.restore()

        context.restore()

        # draw the pie
        x = (bounds.width - rectangles_width) / 2 + rectangles_width
        y = bounds.height / 2
        r = min(bounds.width, bounds.height) / 2 - 10

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

                angle += slice
