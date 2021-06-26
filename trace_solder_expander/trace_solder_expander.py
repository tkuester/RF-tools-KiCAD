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
import math

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

    def __init__(self,  parent):
        SolderExpanderDlg.SolderExpanderDlg.__init__(self, parent)
        self.m_buttonDelete.Bind(wx.EVT_BUTTON, self.onDeleteClick)
        self.SetMinSize(self.GetSize())
    
#

class Solder_Expander(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "Solder Mask Expander for Tracks\nversion 1.7"
        self.category = "Modify PCB"
        self.description = "Solder Mask Expander for selected Tracks on the PCB"
        self.icon_file_name = os.path.join(os.path.dirname(__file__), "./soldermask_clearance.png")
        self.show_toolbar_button = True
        
    def Warn(self, message, caption='Warning!'):
        dlg = wx.MessageDialog(
            None, message, caption, wx.OK | wx.ICON_WARNING)
        dlg.ShowModal()
        dlg.Destroy()

    def CheckInput(self, value, data):
        val = None
        try:
            val = float(value.replace(',','.'))
            if val <= 0:
                raise Exception("Invalid")
        except:
            self.Warn(
                "Invalid parameter for %s: Must be a positive number" % data)
            val = None
        return val

    def Run(self):
        #import pcbnew
        #pcb = pcbnew.GetBoard()
        # net_name = "GND"
        #aParameters = SolderExpanderDlg(None)
        # _pcbnew_frame = [x for x in wx.GetTopLevelWindows() if x.GetTitle().lower().startswith('pcbnew')][0]
        _pcbnew_frame = [x for x in wx.GetTopLevelWindows() if x.GetName() == 'PcbFrame'][0]
        aParameters = SolderExpander_Dlg(_pcbnew_frame)
        aParameters.m_clearanceMM.SetValue("0.2")
        aParameters.m_bitmap1.SetBitmap(wx.Bitmap( os.path.join(os.path.dirname(os.path.realpath(__file__)), "soldermask_clearance_help.png") ) )
        pcb = pcbnew.GetBoard()
        if hasattr(pcb, 'm_Uuid'):
            aParameters.m_buttonDelete.Disable()
        modal_result = aParameters.ShowModal()
        clearance = FromMM(self.CheckInput(aParameters.m_clearanceMM.GetValue(), "extra clearance from track width"))
        if clearance is not None:
            if modal_result == wx.ID_OK:
                #pcb = pcbnew.GetBoard()
                tracks=getSelTracks(pcb)
                if len(tracks) >0: #selected tracks >0
                    solderExpander(pcb,tracks,clearance)
                else:
                    pads=[]
                    for item in pcb.GetPads():
                        if item.IsSelected():
                            pads.append(item)
                    if len(pads) == 1:
                        tracks=[]
                        tracks = find_Tracks_inNet_Pad(pcb,pads[0])
                        c_tracks = get_contiguous_tracks(pcb,tracks,pads[0])
                        solderExpander(pcb,c_tracks,clearance)
                    else:
                        wx.LogMessage("Solder Mask Expander:\nSelect Tracks\nor One Pad to select connected Tracks")
                        
                #solderExpander(clearance)
            elif modal_result == wx.ID_DELETE:
                Delete_Segments(pcb)
                #wx.LogMessage('Solder Mask Segments on Track Net Deleted')
            else:
                None  # Cancel
        else:
            None  # Invalid input
        aParameters.Destroy()


def solderExpander(pcb,tracks,clearance):
        mask_width = clearance #FromMM(.5) # msk espansion value each side
        #mask_layer = pcbnew.F_Mask
        
        # pcb = LoadBoard(in_filename)
        #pcb = pcbnew.GetBoard() 
        
        ToUnits=pcbnew.ToMM #ToMils
        FromUnits=pcbnew.FromMM #Mils
        
        for item in tracks:
            start = item.GetStart()
            end = item.GetEnd()
            width = item.GetWidth()
            layerId = item.GetLayer()
            layer = item.GetLayerSet()
            layerN = item.GetLayerName()
            layer = pcb.GetLayerID(layerN)
            track_net_name = item.GetNetname()
            ts = 0
            for c in track_net_name:
                ts = ts + ord(c)
            #wx.LogMessage("LayerName"+str(layer))

            if layerId == pcbnew.F_Cu:
                mask_layer = pcbnew.F_Mask
            elif layerId == pcbnew.B_Cu: #'B_Cu':
                mask_layer = pcbnew.B_Mask
            else: #we shouldn't arrive here
                mask_layer = pcbnew.F_Mask
            wxLogDebug(" * Track: %s to %s, width %f mask_width %f" % (ToUnits(start),ToUnits(end),ToUnits(width), ToUnits(mask_width)),debug)
            #print (" * Track: %s to %s, width %f mask_width %f" % (ToUnits(start),ToUnits(end),ToUnits(width), ToUnits(mask_width)))
            new_soldermask_line = pcbnew.PCB_SHAPE(pcb)
            new_soldermask_line.SetShape(pcbnew.PCB_SHAPE_TYPE_SEGMENT)
            new_soldermask_line.SetStart(start)
            new_soldermask_line.SetEnd(end)
            new_soldermask_line.SetWidth(width+2*mask_width) #FromUnits(int(mask_width)))
            new_soldermask_line.SetLayer(mask_layer) #pcbnew.F_Mask) #pcb.GetLayerID(mask_layer))
            # again possible to mark via as own since no timestamp_t binding kicad v5.1.4
            if hasattr(new_soldermask_line, 'SetTimeStamp'):
                new_soldermask_line.SetTimeStamp(ts)  # adding a unique number (this netname) as timestamp to mark this via as generated by this script on this netname
            pcb.Add(new_soldermask_line)
            #break;
        pcbnew.Refresh()        
#

def Delete_Segments(pcb):
    draws = []
    #print ("TRACKS WHICH MATCH CRITERIA:")
    for item in pcb.GetDrawings():
    #for item in pcb.GetTracks():
        if type(item) is DRAWSEGMENT and item.IsSelected(): #item.GetNetname() == net_name:
            draws.append(item)
    wxLogDebug(str(len(draws)),debug)
        
    if len (draws) == 1:            
        tsd = draws[0].GetTimeStamp()
        wxLogDebug(str(tsd),debug)
        if tsd != 0:
            target_draws = filter(lambda x: (x.GetTimeStamp() == tsd), pcb.GetDrawings())
            #wx.LogMessage(str(len(target_tracks)))
            target_draws_cp = list(target_draws)
            for i in range(l):
                pcb.RemoveNative(target_draws_cp[i])
            #for draw in target_draws:
            #    #if via.GetTimeStamp() == 55:
            #    pcb.RemoveNative(draw)
                #wx.LogMessage('removing via')
            #pcbnew.Refresh()
            wxLogDebug(u'\u2714 Mask Segments Deleted',True)
        else:
            wxLogDebug(u'\u2718 you must select only Mask segment\n generated by this tool',not debug)
    else:
        #msg = u'\n\u2714 Radius > 3 * (track width)'
        wxLogDebug(u'\u2718 you must select One Mask segment only',not debug)
#
#Solder_Expander().register()

