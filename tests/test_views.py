from pyramid.httpexceptions import HTTPFound
from pyramid_crud.views import CRUDView
from pyramid_crud import forms
from sqlalchemy import Column, String
from webob.multidict import MultiDict
try:
    from unittest.mock import MagicMock
except ImportError:
    from mock import MagicMock
import pytest


@pytest.fixture
def route_setup(config):
    basename = 'tests.test_views.MyView.'
    config.add_route(basename + "list", '/test')
    config.add_route(basename + "edit", '/test/{id}')
    config.add_route(basename + "delete", '/test/delete/{id}')
    config.add_route(basename + "new", '/test/new')


#@pytest.mark.usefixtures("config")
@pytest.fixture
def csrf_token(session, pyramid_request):
    session.get_csrf_token.return_value = 'ABCD'
    token = pyramid_request.session.get_csrf_token()
    pyramid_request.POST['csrf_token'] = token


class TestNormalViewDefaults(object):

    @pytest.fixture(autouse=True)
    def _prepare_view(self, pyramid_request, DBSession, form_factory,
                      model_factory, normal_form):
        self.request = pyramid_request
        self.request.POST = MultiDict(self.request.POST)
        self.Model = model_factory([Column('test_text', String)])
        self.Form = form_factory(model=self.Model, base=normal_form)
        self.request.dbsession = DBSession
        self.session = DBSession

        class MyView(CRUDView):
            Form = self.Form
            url_path = '/test'
        self.View = MyView
        self.view = self.View(self.request)

    @pytest.fixture
    def obj(self):
        obj = self.Model()
        self.session.add(obj)
        self.session.flush()
        assert obj.id
        return obj

    def test_title(self):
        assert self.view.title == "Model"

    def test_title_plural(self):
        assert self.view.title_plural == "Models"

    def test_template_dir(self):
        assert self.view.template_dir == 'default'

    def test_template_ext(self):
        assert self.view.template_ext == '.mako'

    def test_template_base_name(self):
        assert self.view.template_base_name == 'base'

    def test_button_form(self):
        assert self.view.button_form is forms.ButtonForm

    def test_delete_form_factory(self):
        form = self.view.delete_form_factory(self.request.POST,
                                             csrf_context=self.request)
        assert isinstance(form, forms.ButtonForm)

    def test_delete_form(self):
        assert self.view._delete_form is None
        assert isinstance(self.view.delete_form(), forms.ButtonForm)
        assert isinstance(self.view._delete_form, forms.ButtonForm)

    def test__template_for(self):
        self.View.foo_template = "sometemplate.mako"
        assert self.View._template_for("foo") == "sometemplate.mako"

    def test__template_for_default(self):
        assert self.View._template_for("foo") == "default/foo.mako"

    @pytest.mark.usefixtures("route_setup")
    def test_redirect(self):
        redirect = self.view.redirect("tests.test_views.MyView.list")
        assert isinstance(redirect, HTTPFound)
        assert redirect.location == 'http://example.com/test'

    @pytest.mark.usefixtures("route_setup")
    def test_redirect_default(self):
        self.request.matched_route = MagicMock()
        self.request.matched_route.name = 'tests.test_views.MyView.list'
        redirect = self.view.redirect()
        assert isinstance(redirect, HTTPFound)
        assert redirect.location == 'http://example.com/test'

    def test_route_name(self):
        assert self.View.route_name("test") == "tests.test_views.MyView.test"

    def test__get_route_pks(self, obj):
        assert self.view._get_route_pks(obj) == {'id': obj.id}

    def test__get_route_pks_empty_id(self):
        obj = self.Model()
        with pytest.raises(ValueError):
            self.view._get_route_pks(obj)

    @pytest.mark.usefixtures("route_setup")
    def test__delete_route(self, obj):
        route = self.view._delete_route(obj)
        assert route == "http://example.com/test/delete/%d" % obj.id

    @pytest.mark.usefixtures("route_setup")
    def test__edit_route(self, obj):
        route = self.view._edit_route(obj)
        assert route == "http://example.com/test/%d" % obj.id

    def test__get_request_pks(self):
        self.request.matchdict['id'] = 4
        assert self.view._get_request_pks() == {'id': 4}

    def test__get_request_pks_empty(self):
        assert self.view._get_request_pks() is None

    def test_list_empty(self):
        data = self.view.list()
        assert len(data) == 1
        query = data['items']
        assert list(query) == []

    def test_list_obj(self, obj):
        data = self.view.list()
        assert len(data) == 1
        query = data['items']
        items = list(query)
        assert len(items) == 1
        item = items[0]
        assert item == obj

    @pytest.mark.usefixtures("route_setup", "csrf_token")
    def test_delete(self, obj):
        self.request.method = 'POST'
        self.request.matchdict['id'] = obj.id
        redirect = self.view.delete()
        assert isinstance(redirect, HTTPFound)
        flash = self.request.session.flash
        flash.assert_called_once_with('Model deleted!')

    def test_delete_wrong_method(self):
        self.request.method = 'GET'
        with pytest.raises(AssertionError):
            self.view.delete()

    @pytest.mark.usefixtures("route_setup", "csrf_token")
    def test_delete_not_found(self):
        self.request.method = 'POST'
        self.request.matchdict['id'] = 1
        with pytest.raises(HTTPFound):
            self.view.delete()
        flash = self.request.session.flash
        flash.assert_called_once_with('Model not found!', 'error')

    @pytest.mark.usefixtures("route_setup", "session")
    def test_delete_missing_pks(self):
        self.request.method = 'POST'
        with pytest.raises(HTTPFound):
            self.view.delete()
        flash = self.request.session.flash
        flash.assert_called_once_with('Invalid URL', 'error')

    @pytest.mark.usefixtures("csrf_token", "route_setup")
    def test_delete_wrong_token(self):
        self.request.method = 'POST'
        self.request.matchdict['id'] = 1
        self.request.POST['csrf_token'] = 'WRONG'
        with pytest.raises(HTTPFound):
            self.view.delete()
        flash = self.request.session.flash
        flash.assert_called_once_with('Delete failed.', 'error')


# Test with multiple PK
# Test ValueError on get_request_pks for only one PK given