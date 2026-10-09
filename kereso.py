import wx
from theme_manager import apply_theme_from_settings

class KeresoDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Keresés és szűrés")
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        input_sizer = wx.BoxSizer(wx.HORIZONTAL)
        label = wx.StaticText(self, label="Keresett szöveg:")
        self.text_ctrl = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.text_ctrl.Bind(wx.EVT_TEXT_ENTER, self.on_enter)

        input_sizer.Add(label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        input_sizer.Add(self.text_ctrl, 1, wx.ALL | wx.EXPAND, 5)

        # Pontos egyezés jelölőnégyzet
        self.exact_match_cb = wx.CheckBox(self, label="Csak pontos egyezés")

        # Gombok
        ok_button = wx.Button(self, wx.ID_OK, label="Keresés")
        clear_button = wx.Button(self, wx.ID_ANY, label="Mező ürítése")
        cancel_button = wx.Button(self, wx.ID_CANCEL, label="Mégse")

        ok_button.SetDefault()
        clear_button.Bind(wx.EVT_BUTTON, self.on_clear)

        # A tabulátoros sorrend megegyezik a hozzáadás sorrendjével:
        # Keresés -> Mező ürítése -> Mégse
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer(1)
        btn_sizer.Add(ok_button, 0, wx.ALL, 5)
        btn_sizer.Add(clear_button, 0, wx.ALL, 5)
        btn_sizer.Add(cancel_button, 0, wx.ALL, 5)

        # Összeállítás
        main_sizer.Add(input_sizer, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(
            self.exact_match_cb, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10
        )
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Téma alkalmazása, miután minden vezérlő létrejött
        apply_theme_from_settings(self)

        # Az ablak mérete a tartalomhoz igazodik (nagyobb betűméretnél vagy
        # magasabb DPI-nél sem vágódnak le a vezérlők); a minimális
        # szélesség biztosítja, hogy a beviteli mező ne legyen túl keskeny.
        self.SetMinSize((350, -1))
        self.SetSizerAndFit(main_sizer)

        self.CentreOnParent()

    def get_search_text(self):
        """Visszaadja a beírt keresőszöveget."""
        return self.text_ctrl.GetValue()

    def is_exact_match(self):
        """Visszaadja, hogy be van-e jelölve a pontos egyezés."""
        return self.exact_match_cb.IsChecked()

    def on_enter(self, event):
        self.EndModal(wx.ID_OK)

    def on_clear(self, event):
        """Kiüríti a keresőmezőt, és visszaadja rá a fókuszt."""
        self.text_ctrl.Clear()
        self.text_ctrl.SetFocus()
