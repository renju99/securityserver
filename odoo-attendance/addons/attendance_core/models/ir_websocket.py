# -*- coding: utf-8 -*-
from odoo import models


class IrWebsocket(models.AbstractModel):
    _inherit = 'ir.websocket'

    def _build_bus_channel_list(self, channels):
        """Allow HR dashboard clients to subscribe to live attendance bus events."""
        channels = super()._build_bus_channel_list(channels)
        if self.env.user and self.env.user._is_internal():
            if self.env.user.has_group('hr_attendance.group_hr_attendance_manager'):
                channels.append('bw_attendance_hr_live')
        return channels
