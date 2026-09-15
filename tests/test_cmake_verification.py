import json
import shutil
from pathlib import Path
import pytest
from reverend.development.cmake import discover_cmake_checks
from reverend.development.verification import VerificationError, run_verification_plan
from test_development_verification import setup_task


def test_clean_cmake_configures_before_build_and_test(tmp_path):
    checks=discover_cmake_checks(tmp_path)
    assert [c.name for c in checks]==['cmake-configure','cmake-build','ctest']
    assert checks[0].argv==('cmake','-S','.','-B','.reverend-build','-DBUILD_TESTING=ON')
    assert checks[1].argv[-2:]==('--parallel','2')


def test_preset_inheritance_is_projected_to_owned_build(tmp_path):
    (tmp_path/'CMakePresets.json').write_text(json.dumps({'version':3,'configurePresets':[
        {'name':'base','hidden':True,'generator':'Unix Makefiles','cacheVariables':{'BUILD_TESTING':True}},
        {'name':'dev','inherits':'base','binaryDir':'/outside','cacheVariables':{'CMAKE_BUILD_TYPE':'Debug'}}],
        'buildPresets':[{'name':'build','configurePreset':'dev','configuration':'Debug'}]}))
    checks=discover_cmake_checks(tmp_path)
    assert '/outside' not in ' '.join(checks[0].argv)
    assert '-DCMAKE_BUILD_TYPE=Debug' in checks[0].argv
    assert checks[1].argv[-2:]==('--config','Debug')


@pytest.mark.parametrize('config',[
    {'include':['../outside.json']},
    {'configurePresets':[{'name':'dev','inherits':'dev'}]},
    {'configurePresets':[{'name':'dev','environment':{'PATH':'/outside'}}]},
    {'configurePresets':[{'name':'dev','cacheVariables':{'CMAKE_TOOLCHAIN_FILE':'/tmp/toolchain'}}]},
    {'configurePresets':[{'name':'dev'}],'buildPresets':[{'name':'install','configurePreset':'dev','targets':['install']}]},
])
def test_unsupported_or_dangerous_presets_refused(tmp_path,config):
    (tmp_path/'CMakePresets.json').write_text(json.dumps(config))
    with pytest.raises(VerificationError):discover_cmake_checks(tmp_path)


def test_build_symlink_refused(tmp_path):
    (tmp_path/'.reverend-build').symlink_to(tmp_path.parent,target_is_directory=True)
    with pytest.raises(VerificationError):discover_cmake_checks(tmp_path)


@pytest.mark.skipif(not shutil.which('cmake') or not shutil.which('ctest'),reason='CMake tooling unavailable')
@pytest.mark.parametrize('tests,expected',[(True,'passed'),(False,'skipped')])
def test_real_clean_worktree_build_and_ctest(tmp_path,tests,expected):
    context,connection,task,worktree=setup_task(tmp_path)
    try:
        root=Path(worktree.path)
        text='cmake_minimum_required(VERSION 3.16)\nproject(Example NONE)\n'
        if tests:text+='enable_testing()\nadd_test(NAME smoke COMMAND "${CMAKE_COMMAND}" -E true)\n'
        (root/'CMakeLists.txt').write_text(text)
        report=run_verification_plan(connection,task.id,discover_cmake_checks(root))
        assert report.passed
        assert report.checks[-1].status==expected
        assert (root/'.reverend-build/CMakeCache.txt').is_file()
        assert connection.execute('SELECT count(*) FROM verifications').fetchone()[0]==3
    finally:context.__exit__(None,None,None)
