odoo.define('br_point_sale.receipt_nfce', function (require) {
"use strict";


var PosBaseWidget = require('point_of_sale.BaseWidget');
var gui = require('point_of_sale.gui');
var models = require('point_of_sale.models');
var core = require('web.core');
var rpc = require('web.rpc');
var utils = require('web.utils');
var field_utils = require('web.field_utils');

var QWeb = core.qweb;
var _t = core._t;

var round_pr = utils.round_precision;

var screens = require('point_of_sale.screens');

var ReceiptScreenWidget = screens.ScreenWidget.extend({
    template: 'ReceiptScreenWidget',
    show: function(){
        this._super();
        var self = this;

        this.render_change();
        this.render_receipt();
        this.handle_auto_print();
    },

    handle_auto_print: function() {
        if (this.should_close_immediately()){
                this.click_next();
            }
        else {
            this.lock_screen(false);
        }
    },
    should_auto_print: function() {
        return this.pos.config.iface_print_auto && !this.pos.get_order()._printed;
    },
    should_close_immediately: function() {
        return this.pos.config.iface_print_skip_screen;
    },
    lock_screen: function(locked) {
        this._locked = locked;
        if (locked) {
            this.$('.next').removeClass('highlight');
        } else {
            this.$('.next').addClass('highlight');
        }
    },
    get_receipt_render_env: function() {
        var order = this.pos.get_order();
        return {
            widget: this,
            pos: this.pos,
            order: order,
            receipt: order.export_for_printing(),
            orderlines: order.get_orderlines(),
            paymentlines: order.get_paymentlines(),
        };
    },
    print_web: function() {
        window.print();
        var self = this;
        var order = this.pos.get_order();
        var pos_reference = order["name"]
        console.log(order["name"])
        var receipt = rpc.query({
            model: 'report.point_of_sale.report_saledetails',
            method: 'get_danfce',
            args: [pos_reference],
        }).then(function(result) {
            var report = result;
            self.print_receipt(report);
        });

    },
    print_xml: function() {
        var receipt = QWeb.render('XmlReceipt', this.get_receipt_render_env());

        this.pos.proxy.print_receipt(receipt);
        this.pos.get_order()._printed = true;
    },
    print: function() {
        var self = this;

        if (!this.pos.config.iface_print_via_proxy) {

            this.lock_screen(true);

            setTimeout(function(){
                self.lock_screen(false);
            }, 1000);

            this.print_web();
        } else {    // proxy (xml) printing
            this.print_xml();
            this.lock_screen(false);
        }
    },
    click_next: function() {
        this.pos.get_order().finalize();
    },
    click_back: function() {
        // Placeholder method for ReceiptScreen extensions that
        // can go back ...
    },
    renderElement: function() {
        var self = this;
        this._super();
        this.$('.next').click(function(){
            if (!self._locked) {
                self.click_next();
            }
        });
        this.$('.back').click(function(){
            if (!self._locked) {
                self.click_back();
            }
        });
        this.$('.button.print').click(function(){
            if (!self._locked) {
                self.print();
            }
        });
    },
    render_change: function() {
        this.$('.change-value').html(this.format_currency(this.pos.get_order().get_change()));
    },
    render_receipt: function() {
        this.$('.pos-receipt-container').html(QWeb.render('PosTicket', this.get_receipt_render_env()));
    },
});
gui.define_screen({name:'receipt', widget: ReceiptScreenWidget});
});