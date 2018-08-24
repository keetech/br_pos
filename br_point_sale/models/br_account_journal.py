# -*- coding: utf-8 -*-
# © 2016 Raphael Rodrigues <raphael0608@gmail.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from datetime import datetime
from random import SystemRandom
from odoo.addons import decimal_precision as dp
from odoo import api, models, fields

class AccountJournal(models.Model):
    _inherit = 'account.journal'

    payment_mode = fields.Many2one('payment.mode', string='Modo de Pagamento')