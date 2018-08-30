from odoo import api, fields, models, tools, _
from odoo.tools import float_is_zero
from odoo.exceptions import UserError
from odoo.http import request
from odoo.addons import decimal_precision as dp

import pytz
import base64
import logging
from lxml import etree
from io import BytesIO

_logger = logging.getLogger(__name__)


try:
    from pytrustnfe.nfe.danfe import danfe
    from pytrustnfe.nfe.danfce import danfce
except ImportError:
    _logger.warning('Cannot import pytrustnfe', exc_info=True)

class ReportSaleDetails(models.AbstractModel):

    _inherit = 'report.point_of_sale.report_saledetails'

    def _return_pdf_invoice(self, doc):
        if doc.model == '65':
            return 'br_nfe.report_br_nfe_danfe'
        return super(AccountInvoice, self)._return_pdf_invoice(doc)

    def _action_preview_danfe(self, doc):

        report = self._return_pdf_invoice(doc)
        if not report:
            raise UserError(
                'Nenhum relatório implementado para este modelo de documento')
        if not isinstance(report, str):
            return report
        action = self.env.ref(report).report_action(doc)
        return action

    @api.model
    def get_danfce(self, pos_reference=False):
        import pudb;pu.db
        docs = self.env['invoice.eletronic'].search([('pos_order_reference', '=', pos_reference)])

        #return self.env.ref('br_nfe.report_br_nfe_danfe').report_action(docs[0])
        #eport_obj = self.env['model.name'].search([]).ids
        datas = {
            'ids': docs,
            'model': 'invoice.eletronic',
            'form': docs,
        }

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'br_nfe.report_br_nfe_danfe',
            'datas': datas,
        }

        '''
        if not docs:
            raise UserError(u'Não existe um E-Doc relacionado à esta fatura')

        for doc in docs:
            if doc.state not in ('done'):
                raise UserError('Nota Fiscal na fila de envio. Aguarde!')

        if len(docs) > 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'invoice.eletronic.selection.wizard',
                'name': "Escolha a nota a ser impressa",
                'view_mode': 'form',
                'context': self.env.context,
                'target': 'new',
            }
        else:
            action = self.env.ref('br_nfe.report_br_nfe_danfe').report_action(docs[0])

        nfe = self.env['invoice.eletronic'].search([('pos_order_reference', '=', pos_reference)])

        nfe_xml = base64.decodestring(nfe.nfe_processada)

        cce_xml_element = []
        cce_list = self.env['ir.attachment'].search([
            ('res_model', '=', 'invoice.eletronic'),
            ('res_id', '=', nfe.id),
            ('name', 'like', 'cce-')
        ])

        if cce_list:
            for cce in cce_list:
                cce_xml = base64.decodestring(cce.datas)
                cce_xml_element.append(etree.fromstring(cce_xml))

        logo = False
        if nfe.invoice_id.company_id.logo:
            logo = base64.decodestring(nfe.invoice_id.company_id.logo)
        elif nfe.invoice_id.company_id.logo_web:
            logo = base64.decodestring(nfe.invoice_id.company_id.logo_web)

        if logo:
            tmpLogo = BytesIO()
            tmpLogo.write(logo)
            tmpLogo.seek(0)
        else:
            tmpLogo = False

        xml_element = etree.fromstring(nfe_xml)
        obj_danfe = danfe
        if nfe.model == '65':
            obj_danfe = danfce
        oDanfe = obj_danfe(list_xml=[xml_element], logo=tmpLogo)

        tmpDanfe = BytesIO()
        oDanfe.writeto_pdf(tmpDanfe)
        danfe_file = tmpDanfe.getvalue()
        tmpDanfe.close()

        return danfe_file, 'pdf'
        '''