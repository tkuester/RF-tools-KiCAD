#  Copyright 2019 Maurice https://github.com/easyw/

# GNU GENERAL PUBLIC LICENSE
#                        Version 3, 29 June 2007
#
#  Copyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>
#  Everyone is permitted to copy and distribute verbatim copies
#  of this license document, but changing it is not allowed.
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.

# some source tips @
# https://github.com/bpkempke/kicad-scripts
# https://github.com/MitjaNemec/Kicad_action_plugins
# https://github.com/jsreynaud/kicad-action-scripts

import sys
import os

import wx
import pcbnew

from . import SolderExpanderDlg
from .. import util


class SolderExpander_Dlg(SolderExpanderDlg.SolderExpanderDlg):
    # from https://github.com/MitjaNemec/Kicad_action_plugins
    # hack for new wxFormBuilder generating code incompatible with old wxPython
    # noinspection PyMethodOverriding
    def SetSizeHints(self, sz1, sz2):
        if sys.version_info[0] == 2:
            # wxPython 2
            self.SetSizeHintsSz(sz1, sz2)
        else:
            # wxPython 3
            super(SolderExpander_Dlg, self).SetSizeHints(sz1, sz2)

    def onDeleteClick(self, event):
        return self.EndModal(wx.ID_DELETE)

    def __init__(self, parent):
        SolderExpanderDlg.SolderExpanderDlg.__init__(self, parent)
        self.m_buttonDelete.Bind(wx.EVT_BUTTON, self.onDeleteClick)
        self.SetMinSize(self.GetSize())


class Solder_Expander(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "Solder Mask Expander for Tracks\nversion 1.7"
        self.category = "Modify PCB"
        self.description = "Solder Mask Expander for selected Tracks on the PCB"
        self.icon_file_name = os.path.join(
            os.path.dirname(__file__), "./soldermask_clearance.png"
        )
        self.show_toolbar_button = True

    def Warn(self, message, caption="Warning!"):
        dlg = wx.MessageDialog(None, message, caption, wx.OK | wx.ICON_WARNING)
        dlg.ShowModal()
        dlg.Destroy()

    def CheckInput(self, value, data):
        val = None
        try:
            val = float(value.replace(",", "."))
            if val <= 0:
                raise ValueError("Invalid")
        except:
            self.Warn("Invalid parameter for %s: Must be a positive number" % data)
            val = None
        return val

    def Run(self):
        # Create modal dialog
        _pcbnew_frame = [
            x for x in wx.GetTopLevelWindows() if x.GetName() == "PcbFrame"
        ][0]
        aParameters = SolderExpander_Dlg(_pcbnew_frame)
        aParameters.m_clearanceMM.SetValue("0.2")
        aParameters.m_bitmap1.SetBitmap(
            wx.Bitmap(
                os.path.join(
                    os.path.dirname(os.path.realpath(__file__)),
                    "soldermask_clearance_help.png",
                )
            )
        )

        # Prompt user for settings, check output
        modal_result = aParameters.ShowModal()
        clearance = pcbnew.FromMM(
            self.CheckInput(
                aParameters.m_clearanceMM.GetValue(), "extra clearance from track width"
            )
        )
        aParameters.Destroy()

        if clearance is None:
            return

        # Execute
        pcb = pcbnew.GetBoard()
        if modal_result == wx.ID_OK:
            tracks = util.selected_tracks(pcb)
            soldermask_expander(pcb, tracks, clearance)

            pads = list(util.selected_pads(pcb))
            if len(pads) == 1:
                tracks = []
                tracks = util.find_Tracks_inNet_Pad(pcb, pads[0])
                c_tracks = util.get_contiguous_tracks(pcb, tracks, pads[0])
                soldermask_expander(pcb, c_tracks, clearance)
        elif modal_result == wx.ID_DELETE:
            tracks = util.selected_tracks(pcb)
            delete_expansion(pcb, tracks)

        pcbnew.Refresh()

def soldermask_expander(pcb, tracks, mask_width):
    '''
    Creates a collinear PCB segment on a mask layer that sits on top of
    each PCB track
    '''
    for item in tracks:
        # Determine where to put the mask
        layerId = item.GetLayer()
        if layerId == pcbnew.F_Cu:
            mask_layer = pcbnew.F_Mask
        elif layerId == pcbnew.B_Cu:
            mask_layer = pcbnew.B_Mask
        else:
            # Skip tracks on other (ie: inner) layers
            continue

        start = item.GetStart()
        end = item.GetEnd()
        width = item.GetWidth()

        new_soldermask_line = pcbnew.PCB_SHAPE(pcb)
        new_soldermask_line.SetShape(pcbnew.PCB_SHAPE_TYPE_SEGMENT)
        new_soldermask_line.SetStart(start)
        new_soldermask_line.SetEnd(end)
        new_soldermask_line.SetWidth(width + 2 * mask_width)
        new_soldermask_line.SetLayer(mask_layer)

        pcb.Add(new_soldermask_line)


def delete_expansion(pcb, tracks):
    '''
    Deletes all mask segments that have the same start and end points
    as the PCB tracks.
    '''

    # Find all masks on F_Mask and B_Mask that are line segments
    masks = list(filter(lambda dwg:
        isinstance(dwg, pcbnew.PCB_SHAPE) \
        and dwg.GetLayer() in [pcbnew.F_Mask, pcbnew.B_Mask] \
        and dwg.GetShape() == pcbnew.PCB_SHAPE_TYPE_SEGMENT,
        pcb.GetDrawings()))

    # Go through the selected tracks, and check to see if any mask segments
    # are lying directly on top
    for trk in tracks:
        for msk in masks:
            if trk.GetStart() == msk.GetStart() \
                    and trk.GetEnd() == msk.GetEnd():
                # Break here for performance, expect that there will only be
                # one mask segment to delete.
                pcb.RemoveNative(msk)
                break

        # Tidy up python list to speed up the search next time
        masks.remove(msk)
