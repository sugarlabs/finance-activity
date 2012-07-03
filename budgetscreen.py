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
import datetime
import locale

from gettext import gettext as _

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject

# Set up localization.
locale.setlocale(locale.LC_ALL, '')

# Import activity module
import finance

BUDGET_HELP = _(
    'The Budget view allows you to set a monthly budget for each expense '
    'category, and to keep track of your\nbudgets. To set a budget, type '
    'the amount in the box to the right of the category.')


class BudgetScreen(Gtk.VBox):
    def __init__(self, activity):
        GObject.GObject.__init__(self)

        self.activity = activity

        self.category_total = {}
        self.sorted_categories = []

        self.budgetbox = Gtk.VBox()

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add_with_viewport(self.budgetbox)

        self.pack_start(scroll, True, True, 0)

    def build(self):
        # Build the category totals.
        self.category_total = {}
        for t in self.activity.visible_transactions:
            cat = t['category']
            amount = t['amount']

            if t['type'] == 'debit':
                if not cat in self.category_total:
                    self.category_total[cat] = amount
                else:
                    self.category_total[cat] += amount

        # Generate a list of names sorted by total.
        self.sorted_categories = self.category_total.keys()
        self.sorted_categories.sort()

        # Clear all widgets.
        for w in self.budgetbox.get_children():
            self.budgetbox.remove(w)

        # Build header.
        catlabel = Gtk.Label()
        catlabel.set_markup('<b><big>' + _('Category') + '</big></b>')
        spentlabel = Gtk.Label()
        spentlabel.set_markup('<b><big>' + _('Spent') + '</big></b>')
        budgetlabel = Gtk.Label()
        budgetlabel.set_markup('<b><big>' + _('Budget') + '</big></b>')

        headerbox = Gtk.HBox()
        headerbox.pack_start(catlabel, False, True, 20)
        headerbox.pack_start(spentlabel, True, True, 10)
        headerbox.pack_start(budgetlabel, False, True, 20)
        self.budgetbox.pack_start(headerbox, False, False, 10)

        catgroup = Gtk.SizeGroup(Gtk.SizeGroupMode.HORIZONTAL)
        catgroup.add_widget(catlabel)

        spentgroup = Gtk.SizeGroup(Gtk.SizeGroupMode.HORIZONTAL)
        spentgroup.add_widget(spentlabel)

        budgetgroup = Gtk.SizeGroup(Gtk.SizeGroupMode.HORIZONTAL)
        budgetgroup.add_widget(budgetlabel)

        # Build categories.
        for c in self.sorted_categories:
            description = c
            # If there is no category, display as Unknown
            if c is '':
                description = _('Unknown')
            catbox = Gtk.Label(label=description)
            catbox.set_padding(10, 0)

            color = finance.get_category_color_str(c)

            ebox = Gtk.EventBox()
            parse, color = Gdk.Color.parse(color)
            ebox.modify_bg(Gtk.StateType.NORMAL, color)
            ebox.add(catbox)

            catgroup.add_widget(ebox)

            bar = Gtk.DrawingArea()
            bar.connect('draw', self.bar_draw_cb, c)
            spentgroup.add_widget(bar)

            budgetentry = Gtk.Entry()
            budgetentry.connect('changed', self.budget_changed_cb, c)
            budgetentry.set_width_chars(10)
            if c in self.activity.data['budgets']:
                b = self.activity.data['budgets'][c]
                budgetentry.set_text(locale.currency(b['amount'], False))
            budgetgroup.add_widget(budgetentry)

            #freqcombo = Gtk.ComboBoxText()
            #freqcombo.append_text(_('Daily'))
            #freqcombo.append_text(_('Weekly'))
            #freqcombo.append_text(_('Monthly'))
            #freqcombo.append_text(_('Annually'))
            #freqcombo.set_active(2)

            hbox = Gtk.HBox()
            hbox.pack_start(ebox, False, False, 20)
            hbox.pack_start(bar, True, True, 10)
            hbox.pack_start(budgetentry, False, False, 20)
            #hbox.pack_start(freqcombo, True, True, 0)

            self.budgetbox.pack_start(hbox, False, False, 5)

        self.show_all()

        self.activity.set_help(BUDGET_HELP)

    def bar_draw_cb(self, widget, cr, category):
        bounds = widget.get_allocation()

        # Draw amount of time spent in period if sensible.
        period_ratio = None
        if self.activity.period != _('Day') and \
                self.activity.period != _('Forever'):
            period_length = (
                self.activity.get_next_period(self.activity.period_start) - \
                    self.activity.period_start).days
            period_ratio = float(
                (datetime.date.today() - self.activity.period_start).days) / \
                period_length

            if period_ratio > 0:
                cr.set_source_rgb(0.9, 0.9, 0.9)
                cr.rectangle(0, 0, bounds.width * period_ratio, bounds.height)
                cr.fill()

        # Draw outline.
        cr.set_source_rgb(0, 0, 0)
        cr.rectangle(0, 0, bounds.width, bounds.height)
        cr.stroke()

        # Draw arrow and cost.
        total = self.category_total[category]

        if category in self.activity.data['budgets']:
            budget = self.activity.data['budgets'][category]['amount']

            # Convert from monthly budget.
            if self.activity.period == _('Day'):
                budget = budget / 30.0

            elif self.activity.period == _('Week'):
                budget = budget / 4.0

            elif self.activity.period == _('Year'):
                budget = budget * 12.0

            ratio = total / budget

            cr.move_to(5, 5)
            cr.line_to(ratio * (bounds.width - 30), 5)
            cr.line_to(ratio * (bounds.width - 5), bounds.height / 2)
            cr.line_to(ratio * (bounds.width - 30), bounds.height - 5)
            cr.line_to(5, bounds.height - 5)
            cr.close_path()

            if ratio > 1.0:
                cr.set_source_rgb(1.0, 0.6, 0.6)
            elif period_ratio != None and ratio > period_ratio:
                cr.set_source_rgb(0.9, 0.9, 0.6)
            else:
                cr.set_source_rgb(0.6, 1.0, 0.6)
            cr.fill_preserve()

            cr.set_source_rgb(0.5, 0.5, 0.5)
            cr.stroke()

        text = locale.currency(total)

        cr.set_source_rgb(0, 0, 0)

        cr.set_font_size(20)
        x_bearing, y_bearing, width, height = cr.text_extents(text)[:4]

        cr.move_to(20, (bounds.height - height) / 2 - y_bearing)
        cr.show_text(text)

    def budget_changed_cb(self, widget, category):
        text = widget.get_text()
        if text != '':
            self.activity.data['budgets'][category] = {'amount': float(text)}
        else:
            del self.activity.data['budgets'][category]
        self.queue_draw()
