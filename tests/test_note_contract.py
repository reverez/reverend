from reverend.cli import TEMPLATE

def test_master_template_exists():
    assert TEMPLATE.is_file()
