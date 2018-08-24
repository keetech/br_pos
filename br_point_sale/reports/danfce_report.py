# © 2017 Danimar Ribeiro, Trustcode
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import pytz
import base64
import logging
from lxml import etree
from io import BytesIO
from odoo import models

_logger = logging.getLogger(__name__)

try:
    from pytrustnfe.nfe.danfe import danfe
    from pytrustnfe.nfe.danfce import danfce
except ImportError:
    _logger.warning('Cannot import pytrustnfe', exc_info=True)


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def render_qweb_pdf(self, res_ids, data=None):
        if self.report_name != 'br_point_sale.main_template_br_nfe_danfce':
            return super(IrActionsReport, self).render_qweb_pdf(res_ids, data=data)

        nfe = self.env['invoice.eletronic'].search([('id', 'in', res_ids)])

        if nfe.nfe_processada:
            nfe_xml = base64.decodestring(nfe.nfe_processada)
        else:
            nfe_xml = base64.decodestring(nfe.xml_to_send)

        tmpLogo = False

        xml_element = etree.fromstring(nfe_xml)

        obj_danfe = danfce

        oDanfe = obj_danfe(list_xml=[xml_element], logo=tmpLogo)

        tmpDanfe = BytesIO()
        oDanfe.writeto_pdf(tmpDanfe)
        danfe_file = tmpDanfe.getvalue()
        tmpDanfe.close()

        return danfe_file, 'pdf'