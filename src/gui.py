#!/usr/bin/env python

# Copyright 2007 Jonas Bengtsson

# This file is part of autocrc.

# autocrc is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# autocrc is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os, sys, threading, urllib
import wx
import wx.lib.mixins.listctrl as listmix
import autocrc

EVT_UPDATE_ID = wx.NewId()
EVT_START_ID = wx.NewId()
EVT_END_ID = wx.NewId()
EVT_FILE_START_ID = wx.NewId()
EVT_FILE_UPDATE_ID = wx.NewId()

class UpdateEvent(wx.PyEvent):
    "Generated when autocrc has CRC-checked a file"
    def __init__(self, dirname, fname, status, colour=None):
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_UPDATE_ID)
        self.dirname = dirname
        self.fname = fname
        self.status = status
        self.colour = colour

class StartEvent(wx.PyEvent):
    "Generated when the CRC-checking starts"
    def __init__(self, totalnrfiles):
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_START_ID)
        self.totalnrfiles = totalnrfiles


class EndEvent(wx.PyEvent):
    "Generated when the CRC-checking has finished"
    def __init__(self, everythingok):
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_END_ID)
        self.everythingok = everythingok

class FileStartEvent(wx.PyEvent):
    "Generated when the CRC-checking of a file starts"
    def __init__(self, nrblocks):
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_FILE_START_ID)
        self.nrblocks = nrblocks

class FileUpdateEvent(wx.PyEvent):
    "Generated when a block of a file has been CRC-checked"
    def __init__(self):
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_FILE_UPDATE_ID)

class GuiModel(autocrc.Model):
    "Generats events used by the gui"
    def __init__(self, receiver, *args, **kargs):
        autocrc.Model.__init__(self, *args, **kargs)
        self.dirname = None
        self.dirstat = None
        self.receiver = receiver
        self.want_abort = False

    def directorystart(self, dirname, dirstat):
        "Called when the CRC-checks on a directory is started"
        self.dirname = dirname
        self.dirstat = dirstat

    def fileok(self, fname):
        "Called when a file was successfully CRC-checked"
        wx.PostEvent(self.receiver, UpdateEvent(self.dirname, fname, "OK"))

    def filemissing(self, fname):
        "Called when a file is missing"
        wx.PostEvent(self.receiver, 
            UpdateEvent(self.dirname, fname, "No such file", wx.BLUE))

    def filereaderror(self, fname):
        "Called when a read error occurs on a file"    
        wx.PostEvent(self.receiver,
            UpdateEvent(self.dirname, fname, "Read error", wx.RED))

    def filedifferent(self, fname, crc, realcrc):
        "Called when a CRC-mismatch occurs"
        wx.PostEvent(self.receiver,
                UpdateEvent(self.dirname, fname, "CRC mismatch", wx.RED))

    def start(self):
        "Called when CRC-checking starts"
        
        totalnrfiles = len(autocrc.getcrcs(os.getcwd(), 
            self.fnames, self.flags)) 
        for dirname in self.dirnames:
            if self.flags.recursive:
                for dirpath, dirnames, filenames in os.walk(dirname):
                    totalnrfiles += len(autocrc.getcrcs(dirpath,
                            os.listdir(dirpath), self.flags))
            else:
                totalnrfiles += len(autocrc.getcrcs(dirname,
                    os.listdir(dirname), self.flags))
        
        wx.PostEvent(self.receiver, StartEvent(totalnrfiles))

    def end(self):
        "Called when the CRC-checking is complete"
        wx.PostEvent(self.receiver, EndEvent(self.totalstat.everythingok()))

    def filestart(self, fileobj):
        nrbytes = os.fstat(fileobj.fileno()).st_size
        nrblocks = nrbytes / self.blocksize

        wx.PostEvent(self.receiver, FileStartEvent(nrblocks))

    def blockread(self):
        if(self.want_abort):
            sys.exit()
        else:
            wx.PostEvent(self.receiver, FileUpdateEvent())

    def abort(self):
        self.want_abort = True

class ButtonPanel(wx.Panel):
    def __init__(self, parent, *args, **kargs):
        wx.Panel.__init__(self, parent, *args, **kargs)

        sizer = wx.BoxSizer()
        
        self.startbutton = wx.Button(self, label='Start')
        self.clearbutton = wx.Button(self, label='Clear')
        self.stopbutton = wx.Button(self, wx.ID_STOP)
        self.quitbutton = wx.Button(self, wx.ID_EXIT)
        
        self.startbutton.Bind(wx.EVT_BUTTON, parent.OnStartButton)
        self.clearbutton.Bind(wx.EVT_BUTTON, parent.OnClearButton)
        self.stopbutton.Bind(wx.EVT_BUTTON, parent.OnStopButton)
        self.quitbutton.Bind(wx.EVT_BUTTON, parent.OnQuitButton)

        sizer.Add(self.startbutton, flag=wx.RIGHT, border=5)
        sizer.Add(self.clearbutton, flag=wx.RIGHT, border=5)
        sizer.Add(self.stopbutton, flag=wx.RIGHT, border=5)
        sizer.Add(self.quitbutton)
        
        self.SetSizer(sizer)

class CheckPanel(wx.Panel):
    def __init__(self, *args, **kargs):
        wx.Panel.__init__(self, *args, **kargs)
        
        sizer = wx.BoxSizer()
        leftsizer = wx.BoxSizer(wx.VERTICAL)
        rightsizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(rightsizer, flag=wx.ALIGN_RIGHT)
        sizer.Add(leftsizer)
        
        self.crcbox = wx.CheckBox(self, 
                label="Parse CRC-sums from filenames")
        self.sfvbox = wx.CheckBox(self, 
                label="Parse CRC-sums from sfv-files")
        self.recbox = wx.CheckBox(self, 
                label="Recursive CRC-checking")
        
        self.crcbox.SetValue(True)
        self.sfvbox.SetValue(True)
        
        rightsizer.Add(self.crcbox)
        leftsizer.Add(self.sfvbox)
        rightsizer.Add(self.recbox)

        self.casebox = wx.CheckBox(self, label="Ignore case")
        self.exchangebox = wx.CheckBox(self, 
            label="Treat Windows directories as Unix directories")
        leftsizer.Add(self.exchangebox)
        rightsizer.Add(self.casebox)
        
        if sys.platform.startswith('win'):
            self.casebox.Hide()
            self.exchangebox.Hide()
        
        self.SetSizer(sizer)

    def flags(self):
        return autocrc.Flags(
                recursive=self.recbox.GetValue(),
                case=not self.casebox.GetValue(),
                exchange=self.exchangebox.GetValue(),
                crc=self.crcbox.GetValue(),
                sfv=self.sfvbox.GetValue())

class OutputList(wx.ListCtrl, 
        listmix.ListCtrlAutoWidthMixin, listmix.ColumnSorterMixin):
    def __init__(self, parent):
        wx.ListCtrl.__init__(self, parent, style=wx.LC_REPORT | 
                wx.LC_HRULES | wx.LC_VRULES | wx.LC_SORT_ASCENDING)
        listmix.ListCtrlAutoWidthMixin.__init__(self)
        listmix.ColumnSorterMixin.__init__(self, 3)
        self.InsertColumn(0, "Directory")
        self.InsertColumn(1, "File")
        self.InsertColumn(2, "Status")
        self.SetColumnWidth(0, 200)
        self.SetColumnWidth(1, 400)
        self.SetColumnWidth(2, 100)
        self.itemDataMap = {}

    def update(self, dirname, fname, status, colour):        
        index = self.InsertStringItem(0, dirname)
        self.SetStringItem(index, 1, fname)
        self.SetStringItem(index, 2, status)

        key = len(self.itemDataMap)
        self.SetItemData(index, key)
        self.itemDataMap[key] = dirname, fname, status
        
        if colour:
            self.SetItemBackgroundColour(index, colour)

    def GetListCtrl(self):
        return self

class DirectoryLabel(wx.TextCtrl):
    def __init__(self, parent):
        wx.TextCtrl.__init__(self, parent, style=wx.NO_BORDER | wx.TE_READONLY)
        
        self.parent = parent
        
        self.SetBackgroundColour(parent.GetBackgroundColour())
        self.update()

    def update(self):
        self.SetValue("%d files and %d directories selected" % \
                (len(self.parent.fnames), len(self.parent.dirnames)))

class DirectoryPanel(wx.Panel, wx.FileDropTarget):
    def __init__(self, *args, **kargs):
        wx.Panel.__init__(self, *args, **kargs)
        wx.FileDropTarget.__init__(self)

        self.fnames = set()
        self.dirnames = set()

        sizer = wx.BoxSizer()

        self.dirbutton = wx.Button(self, label="Add directory")
        self.filebutton = wx.Button(self, label="Add files")
        self.clearbutton = wx.Button(self, label="Clear")
        self.label = DirectoryLabel(self)
        
        self.dirbutton.Bind(wx.EVT_BUTTON, self.OnDirButton)
        self.filebutton.Bind(wx.EVT_BUTTON, self.OnFileButton)
        self.clearbutton.Bind(wx.EVT_BUTTON, self.OnClearButton)

        sizer.Add(self.dirbutton, flag=wx.RIGHT, border=5)
        sizer.Add(self.filebutton, flag=wx.RIGHT, border=5)
        sizer.Add(self.label, proportion=1)
        sizer.Add(self.clearbutton)
        
        self.SetSizer(sizer)

    def OnDropFiles(self, x, y, urlnames):
        for urlname in urlnames:
            #Some filemanagers uses paths that are encoded as urls
            fname = urllib.unquote_plus(urlname)
            if os.path.isfile(fname):
                self.fnames.add(fname)
            elif os.path.isdir(fname):
                self.dirnames.add(fname)
        self.label.update()
    
    def OnClearButton(self, event):
        #clear() isn't good enough since fnames and dirnames 
	#might be used by the model
        self.fnames = set()
        self.dirnames = set()
        self.label.update()

    def OnDirButton(self, event):
        dialog = wx.DirDialog(self, style=wx.DD_DIR_MUST_EXIST)

        if dialog.ShowModal() == wx.ID_OK:
            dirname = dialog.GetPath()
            if type(dirname) is unicode:
                dirname = dirname.encode('latin1','replace')
            self.dirnames.add(dirname)
        self.label.update()

    def OnFileButton(self, event):
        dialog = wx.FileDialog(self, style=wx.FD_MULTIPLE | wx.FD_CHANGE_DIR)

        if dialog.ShowModal() == wx.ID_OK:
            fnames = dialog.GetFilenames()
            for fname in fnames:
                if not type(fname) is unicode:
                    break
                fname = fname.encode('latin1','replace')
            self.fnames.update(fnames)
        self.label.update()

class Gui(wx.Frame):
    def __init__(self, *arg, **karg):
        wx.Frame.__init__(self, *arg, **karg)
        self.running = False

        sizer = wx.BoxSizer(orient=wx.VERTICAL)
        
        self.checkpanel = CheckPanel(self)
        self.dirpanel = DirectoryPanel(self)
        self.buttonpanel = ButtonPanel(self)
        self.text = OutputList(self)
        self.filegauge = wx.Gauge(self)
        self.gauge = wx.Gauge(self)
        self.status = wx.StatusBar(self)

        sizer.Add(self.checkpanel, flag=wx.EXPAND)
        sizer.Add(self.dirpanel, flag=wx.EXPAND)
        sizer.Add(self.text, proportion=1, flag=wx.EXPAND)
        sizer.Add(self.filegauge, flag=wx.EXPAND)
        sizer.Add(self.gauge, flag=wx.EXPAND)
        sizer.Add(self.buttonpanel, flag=wx.EXPAND)
        sizer.Add(self.status, flag=wx.EXPAND)

        self.SetSizer(sizer)
        self.SetDropTarget(self.dirpanel)

        self.Connect(-1, -1, EVT_UPDATE_ID, self.OnUpdate)
        self.Connect(-1, -1, EVT_END_ID, self.OnEnd)
        self.Connect(-1, -1, EVT_START_ID, self.OnStart)
        self.Connect(-1, -1, EVT_FILE_START_ID, self.OnFileStart)
        self.Connect(-1, -1, EVT_FILE_UPDATE_ID, self.OnFileUpdate)

    def OnStart(self, event):
        self.text.DeleteAllItems()

        self.status.SetStatusText("CRC-checking in progress")
        self.running = True

        self.gauge.SetRange(event.totalnrfiles)
        self.gauge.SetValue(0)

    def OnUpdate(self, event):
        "Adds an item to the list and update the gauge"
        self.text.update(event.dirname, event.fname, event.status, event.colour)
        self.gauge.SetValue(self.gauge.GetValue() + 1)

    def OnEnd(self, event):
        if self.model.totalstat.nrfiles == 0:
            self.status.SetStatusText("No CRC-sums found")
        else:
            if event.everythingok:
                message = "Everything OK"
            else:
                message = "Errors occured"
            self.status.SetStatusText("CRC-checking complete. " + message)
        
        self.running = False

    def OnFileStart(self, event):
        self.filegauge.SetRange(event.nrblocks)
        self.filegauge.SetValue(0)

    def OnFileUpdate(self, event):
        self.filegauge.SetValue(self.filegauge.GetValue() + 1)

    def OnStartButton(self, event):
        if self.running:
            self.status.SetStatusText("CRC-checking already running")
            return

        self.status.SetStatusText("Preparing CRC-checking")

        self.model = GuiModel(self,
                flags=self.checkpanel.flags(),
                dirnames=self.dirpanel.dirnames,
                fnames=self.dirpanel.fnames,
                blocksize=1048576)

        try:
            threading.Thread(target=self.model.run).start()
        except threading.ThreadError, eobj:
            self.running = False
            self.status.SetStatusText(eobj.message)
        except OSError, eobj:
            self.running = False
            self.status.SetStatusText(eobj.filename + ":", eobj.message)

    def OnClearButton(self, event):
        self.text.DeleteAllItems()

        if not self.running:
            self.status.SetStatusText("")
            self.gauge.SetValue(0)
            self.filegauge.SetValue(0)

    def OnStopButton(self, event):
        if self.running:
            self.model.abort()
            self.running = False
            self.status.SetStatusText("CRC-checking stopped")
        else:
            self.status.SetStatusText("No CRC-checking to stop")

    def OnQuitButton(self, event):
        self.Close()

def main():
    app = wx.App()
    frame = Gui(None, title="autocrc", size=(700, 700))
    frame.Show()
    app.MainLoop()

if __name__ == "__main__":
    main()
