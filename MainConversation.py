'''a module that define classes to build the conversation widget'''
import gtk
import pango
import gobject

import gui
import utils

from RichBuffer import RichBuffer
from e3 import Message

class MainConversation(gtk.Notebook):
    '''the main conversation, it only contains other widgets'''

    def __init__(self, session):
        '''class constructor'''
        gtk.Notebook.__init__(self)
        self.set_scrollable(True)
        self.popup_enable()

        self.session = session
        self.conversations = {}
        if self.session:
            self.session.protocol.connect('conv-message', 
                self._on_message)
            self.session.protocol.connect('conv-contact-joined', 
                self._on_contact_joined)
            self.session.protocol.connect('conv-contact-left', 
                self._on_contact_left)
            self.session.protocol.connect('conv-group-started', 
                self._on_group_started)
            self.session.protocol.connect('conv-group-ended', 
                self._on_group_ended)

    def _on_message(self, protocol, args):
        '''called when a message is received'''
        (cid, account, message) = args
        conversation = self.conversations.get(cid, None)

        if conversation and message.type == Message.TYPE_MESSAGE:
            contact = self.session.contacts.get(account)

            if contact:
                nick = contact.display_name
            else:
                nick = account

            conversation.output.buffer.put_text(nick + ': ', bold=True)
            conversation.output.buffer.put_text(message.body + '\n', 
                *self.format_from_message(message))
        elif not conversation:
            print 'conversation', cid, 'not found'

    def _on_contact_joined(self, protocol, args):
        '''called when a contact join the conversation'''
        (cid, account) = args
        conversation = self.conversations.get(cid, None)

        if conversation:
            conversation.on_contact_joined(account)

    def _on_contact_left(self, protocol, args):
        '''called when a contact leaves the conversation'''
        (cid, account) = args
        conversation = self.conversations.get(cid, None)

        if conversation:
            conversation.on_contact_left(account)

    def _on_group_started(self, protocol, args):
        '''called when a group conversation starts'''
        cid = args[0]
        conversation = self.conversations.get(cid, None)

        if conversation:
            conversation.on_group_started()

    def _on_group_ended(self, protocol, args):
        '''called when a group conversation ends'''
        cid = args[0]
        conversation = self.conversations.get(cid, None)

        if conversation:
            conversation.on_group_ended()

    def format_from_message(self, message):
        '''return a tuple containing all the format arguments received by
        RichBuffer.put_text'''
        stl = message.style

        result = ('#' + stl.color.to_hex(), None, stl.font, None, stl.bold, 
            stl.italic, stl.underline, stl.strike)
        return result

    def new_conversation(self, cid, members=None):
        '''create a new conversation widget and append it to the tabs'''
        label = gtk.Label('conversation')
        label.set_ellipsize(pango.ELLIPSIZE_END)

        conversation = Conversation(self.session, cid, label, members)
        self.conversations[cid] = conversation
        self.append_page(conversation, label)
        self.set_tab_label_packing(conversation, True, True, gtk.PACK_START)
        self.set_tab_reorderable(conversation, True)
        return conversation

class Conversation(gtk.VBox):
    '''a widget that contains all the components inside'''

    def __init__(self, session, cid, tab_label, members=None):
        '''constructor'''
        gtk.VBox.__init__(self)
        self.session = session
        self.tab_label = tab_label
        self.cid = cid

        if members is None:
            self.members = []
        else:
            self.members = members

        self.panel = gtk.VPaned()
        self.header = Header()
        self.output = OutputText()
        self.input = InputText(self._on_send_message)
        self.info = ContactInfo()

        self.panel.pack1(self.output, True, False)
        self.panel.pack2(self.input)

        hbox = gtk.HBox()
        hbox.pack_start(self.panel, True, True)
        hbox.pack_start(self.info, False)

        self.pack_start(self.header, False)
        self.pack_start(hbox, True, True)

        self.temp = self.panel.connect('map-event', self._on_panel_show)

        if len(self.members) == 0:
            self.header.information = Header.INFO_TEMPLATE % \
                ('account@host.com', 'this is my personal message')
        elif len(self.members) == 1:
            self.set_data(self.members[0])
        else:
            self.set_group_data()

        self.header.set_image(gui.theme.user)
        self.info.first = utils.safe_gtk_image_load(gui.theme.logo)
        self.info.last = utils.safe_gtk_image_load(gui.theme.logo)

    def _on_panel_show(self, widget, event):
        '''callback called when the panel is shown, resize the panel'''
        position = self.panel.get_position()
        self.panel.set_position(position + int(position * 0.5))
        self.panel.disconnect(self.temp)
        del self.temp

    def _on_send_message(self, text):
        '''method called when the user press enter on the input text'''
        self.session.protocol.do_send_message(self.cid, text)
        nick = self.session.contacts.me.display_name
        self.output.buffer.put_text(nick + ': ', bold=True)
        self.output.buffer.put_text(text + '\n')

    def on_contact_joined(self, account):
        '''called when a contact joins the conversation'''
        if account not in self.members:
            self.members.append(account)

            if len(self.members) == 1:
                self.set_data(account)
            else:
                self.set_group_data()

    def on_contact_left(self, account):
        '''called when a contact lefts the conversation'''
        if account in self.members:
            self.members.remove(account)

            if len(self.members) == 1:
                self.set_data(self.members[0])
            else:
                self.set_group_data()

    def on_group_started(self):
        '''called when a group conversation starts'''
        self.set_group_data()

    def on_group_ended(self):
        '''called when a group conversation ends'''
        self.header.set_image(gui.theme.user)

        if len(self.members) == 1:
            self.set_data(self.members[0])

    def set_data(self, account):
        '''set the data of the conversation to the data of the account'''
        contact = self.session.contacts.get(account)

        if contact:
            message = gobject.markup_escape_text(contact.message)
            nick = gobject.markup_escape_text(contact.display_name)
        else:
            message = ''
            nick = account

        self.header.information = Header.INFO_TEMPLATE % (nick, message)
        self.tab_label.set_markup(nick)

    def set_group_data(self):
        '''set the data of the conversation to reflect a group chat'''
        self.header.set_image(gui.theme.users)
        text = 'group chat'

        self.header.information = Header.INFO_TEMPLATE % \
            (text, '%d members' % (len(self.members) + 1,))

        self.tab_label.set_text(text)

class TextBox(gtk.ScrolledWindow):
    '''a text box inside a scroll that provides methods to get and set the
    text in the widget'''

    def __init__(self):
        '''constructor'''
        gtk.ScrolledWindow.__init__(self)
        self.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        self.set_shadow_type(gtk.SHADOW_IN)
        self.textbox = gtk.TextView()
        self.textbox.set_wrap_mode(gtk.WRAP_WORD)
        self.textbox.show()
        self.buffer = self.textbox.get_buffer()
        self.add(self.textbox)

    def clear(self):
        '''clear the content'''
        self.buffer.set_text('')

    def append(self, text):
        '''append text to the widget'''
        end_iter = self.buffer.get_end_iter()
        self.buffer.insert(end_iter, text)

    def _set_text(self, text):
        '''set the text on the widget'''
        self.buffer.set_text(text)

    def _get_text(self):
        '''return the text of the widget'''
        start_iter = self.buffer.get_start_iter()
        end_iter = self.buffer.get_end_iter()
        return self.buffer.get_text(start_iter, end_iter, True)

    text = property(fget=_get_text, fset=_set_text)

class InputText(TextBox):
    '''a widget that is used to insert the messages to send'''

    def __init__(self, on_send_message):
        '''constructor'''
        TextBox.__init__(self)
        self.on_send_message = on_send_message

        self.buffer = RichBuffer()
        self.textbox.set_buffer(self.buffer)

        self.textbox.connect('key-press-event', self._on_key_press_event)

    def _on_key_press_event(self, widget, event):
        '''method called when a key is pressed on the input widget'''
        if event.keyval == gtk.keysyms.Return:
            self.on_send_message(self.text)
            self.text = ''
            return True

class OutputText(TextBox):
    '''a widget that is used to display the messages on the conversation'''

    def __init__(self):
        '''constructor'''
        TextBox.__init__(self)
        self.textbox.set_editable(False)
        self.buffer = RichBuffer()
        self.textbox.set_buffer(self.buffer)

class Header(gtk.HBox):
    '''a widget used to display some information about the conversation'''
    INFO_TEMPLATE = '%s\n<span size="small">%s</span>'

    def __init__(self):
        '''constructor'''
        gtk.HBox.__init__(self)
        self._information = gtk.Label('info')
        self._information.set_alignment(0.0, 0.5)
        self.image = gtk.Image()

        self.pack_start(self._information, True, True)
        self.pack_start(self.image, False)

    def set_image(self, path):
        '''set the image from path'''
        self.remove(self.image)
        self.image = utils.safe_gtk_image_load(path)
        self.pack_start(self.image, False)
        self.image.show()

    def _set_information(self, text):
        '''set the text on the information'''
        self._information.set_markup(text)

    def _get_information(self):
        '''return the text on the information'''
        return self._information.get_markup()

    information = property(fget=_get_information, fset=_set_information)

class ContactInfo(gtk.VBox):
    '''a widget that contains the display pictures of the contacts and our
    own display picture'''

    def __init__(self, first=None, last=None):
        gtk.VBox.__init__(self)
        self._first = first
        self._last = last

        self._first_alig = None
        self._last_alig = None

    def _set_first(self, first):
        '''set the first element and add it to the widget (remove the 
        previous if not None'''

        if self._first_alig is not None:
            self.remove(self._first_alig)

        self._first = first
        self._first_alig = gtk.Alignment(xalign=0.5, yalign=0.0, xscale=1.0,
            yscale=0.1)
        self._first_alig.add(self._first)
        self.pack_start(self._first_alig)

    def _get_first(self):
        '''return the first widget'''
        return self._first

    first = property(fget=_get_first, fset=_set_first)

    def _set_last(self, last):
        '''set the last element and add it to the widget (remove the 
        previous if not None'''

        if self._last_alig is not None:
            self.remove(self._last_alig)

        self._last = last
        self._last_alig = gtk.Alignment(xalign=0.5, yalign=1.0, xscale=1.0,
            yscale=0.1)
        self._last_alig.add(self._last)
        self.pack_start(self._last_alig)

    def _get_last(self):
        '''return the last widget'''
        return self._last

    last = property(fget=_get_last, fset=_set_last)

if __name__ == '__main__':
    import gui
    mconv = MainConversation(None) 
    conv = mconv.new_conversation()
    mconv.new_conversation()
    window = gtk.Window()
    window.add(mconv)
    window.set_default_size(640, 480)
    mconv.show_all()
    window.show()
    gtk.main()