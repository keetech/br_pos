odoo.define('br_point_sale.danfce', function (require) {
"use strict";

var core = require('web.core');
var devices = require('point_of_sale.devices');
var rpc = require('web.rpc');
var PosBaseWidget = require('point_of_sale.BaseWidget');


var QWeb = core.qweb;
var _t = core._t;

    devices.ProxyDevice = devices.ProxyDevice.extend({
        print_sale_details: function() {
            var self = this;
            rpc.query({
                    model: 'report.point_of_sale.report_saledetails',
                    method: 'get_sale_details',
                })
                .then(function(result){
                    var env = {
                        widget: new PosBaseWidget(self),
                        company: self.pos.company,
                        pos: self.pos,
                        products: result.products,
                        payments: result.payments,
                        taxes: result.taxes,
                        total_paid: result.total_paid,
                        date: (new Date()).toLocaleString(),
                    };
                    var report = QWeb.render('SaleDetailsReport', env);
                    self.print_receipt(report);
                });
            });
        },
    });
});