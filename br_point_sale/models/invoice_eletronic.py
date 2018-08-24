from odoo import api, fields, models, tools

class InvoiceEletronic(models.Model):

    _inherit = 'invoice.eletronic'

    # Referêncis Order do POS
    pos_order_reference = fields.Char(u'POS Order Reference', readonly=True)