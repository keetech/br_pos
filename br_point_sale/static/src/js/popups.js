odoo.define('br_point_sale.br_popups', function (require) {
    "use strict";

    var PopupWidget = require('point_of_sale.popups');
    var gui = require('point_of_sale.gui');
    var _t  = require('web.core')._t;

    var NumpadCPF = PopupWidget.extend({
        template: 'NumpadWidget',
        show: function(options){
            options = options || {};
            this._super(options);

            this.inputbuffer = '' + (options.value   || '');
            /* this.decimal_separator = _t.database.parameters.decimal_point; */
            this.renderElement();
            this.firstinput = true;
        },
        click_numpad: function(event){
            var newbuf = this.gui.numpad_input(
                this.inputbuffer,
                $(event.target).data('action'),
                {'firstinput': this.firstinput});

            this.firstinput = (newbuf.length === 0);

            if (newbuf !== this.inputbuffer) {
                this.inputbuffer = newbuf;
                this.$('.value').text(this.inputbuffer);
            }
        },

        click_confirm: function(){
            this.gui.close_popup();
            if( this.options.confirm ){
                this.options.confirm.call(this,this.inputbuffer);
            }
        },
    });

    gui.define_popup({name:'number-cpf', widget: NumpadCPF});

});