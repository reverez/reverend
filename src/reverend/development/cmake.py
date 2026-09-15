"""Conservative CMake preset projection into bounded, argv-only verification."""
from __future__ import annotations

import json
import re
from pathlib import Path

BUILD_DIRECTORY = '.reverend-build'


def _presets(data: dict, key: str) -> dict[str, dict]:
    rows = data.get(key, [])
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError(f'Invalid {key}')
    result = {}
    for row in rows:
        if not isinstance(row, dict) or not re.fullmatch(r'[\w.-]{1,100}', str(row.get('name', ''))):
            raise ValueError('Invalid preset name')
        if row['name'] in result:
            raise ValueError('Duplicate preset name')
        result[row['name']] = row
    return result


def _resolve(name: str, presets: dict, seen: tuple = ()) -> dict:
    if name in seen or len(seen) >= 16 or name not in presets:
        raise ValueError('Invalid or cyclic preset inheritance')
    own = presets[name]
    parents = own.get('inherits', [])
    if isinstance(parents, str):
        parents = [parents]
    if not isinstance(parents, list):
        raise ValueError('Invalid preset inheritance')
    result = {}
    for parent in reversed(parents):
        resolved = _resolve(parent, presets, (*seen, name))
        cache = {**result.get('cacheVariables', {}), **resolved.get('cacheVariables', {})}
        result.update(resolved)
        result['cacheVariables'] = cache
    cache = {**result.get('cacheVariables', {}), **own.get('cacheVariables', {})}
    result.update(own)
    result['cacheVariables'] = cache
    return result


def discover_cmake_checks(root: Path) -> tuple:
    from .verification import VerificationCheck, VerificationError
    build = root / BUILD_DIRECTORY
    if build.is_symlink() or (build.exists() and not build.is_dir()):
        raise VerificationError('Reverend CMake build directory is unsafe')
    cache = build / 'CMakeCache.txt'
    if cache.is_symlink():
        raise VerificationError('CMake cache cannot be a symlink')
    argv = ['cmake', '-S', '.', '-B', BUILD_DIRECTORY, '-DBUILD_TESTING=ON']
    configuration = None
    targets: list[str] = []
    path = root / 'CMakePresets.json'
    if path.exists():
        try:
            if path.is_symlink() or path.stat().st_size > 128 * 1024:
                raise ValueError('Preset file must be bounded and local')
            data = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('include'):
                raise ValueError('External preset includes are not automatically executed')
            presets = _presets(data, 'configurePresets')
            visible = [name for name, row in presets.items() if not row.get('hidden')]
            if visible:
                name = visible[0]
                preset = _resolve(name, presets)
                if preset.get('environment') or preset.get('condition') or preset.get('toolchainFile'):
                    raise ValueError('Environment, conditional, and toolchain presets require explicit review')
                generator = preset.get('generator')
                if generator:
                    if generator not in ('Ninja', 'Ninja Multi-Config', 'Unix Makefiles'):
                        raise ValueError('Unsupported generator')
                    argv.extend(['-G', generator])
                for key, value in preset.get('cacheVariables', {}).items():
                    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key):
                        raise ValueError('Invalid cache key')
                    if value is None:
                        continue
                    if isinstance(value, dict):
                        value = value.get('value')
                    if isinstance(value, bool):
                        value = 'ON' if value else 'OFF'
                    if not isinstance(value, (str, int)):
                        raise ValueError('Invalid cache value')
                    value = str(value)
                    if len(value) > 4096 or '$' in value or '\x00' in value:
                        raise ValueError('Unsupported cache expansion')
                    if any(part in key for part in ('TOOLCHAIN', 'PROJECT_INCLUDE', 'MAKE_PROGRAM')):
                        raise ValueError('Executable/toolchain cache overrides require explicit review')
                    argv.append(f'-D{key}={value}')
                for row in _presets(data, 'buildPresets').values():
                    if row.get('configurePreset') == name and not row.get('hidden'):
                        if row.get('environment') or row.get('inherits') or row.get('condition'):
                            raise ValueError('Complex build presets require explicit review')
                        configuration = row.get('configuration')
                        targets = row.get('targets', [])
                        if isinstance(targets, str):
                            targets = [targets]
                        if not isinstance(targets, list) or any(
                            not isinstance(t, str) or not re.fullmatch(r'[\w.+-]+', t)
                            or t.lower() in {'install', 'package', 'uninstall'} for t in targets
                        ):
                            raise ValueError('Unsafe build targets')
                        break
                # Test preset configuration is honoured; arbitrary filters/options
                # are deliberately not translated into tool authority.
                for row in _presets(data, 'testPresets').values():
                    if row.get('configurePreset') == name and not row.get('hidden'):
                        if any(row.get(k) for k in ('environment', 'inherits', 'condition', 'filter')):
                            raise ValueError('Complex test presets require explicit review')
                        configuration = row.get('configuration', configuration)
                        break
        except (ValueError, TypeError, KeyError, OSError) as exc:
            raise VerificationError(f'CMake preset discovery refused: {exc}') from exc
    if configuration is not None and (not isinstance(configuration, str) or not re.fullmatch(r'[\w.-]+', configuration)):
        raise VerificationError('Invalid CMake configuration')
    build_argv = ['cmake', '--build', BUILD_DIRECTORY, '--parallel', '2']
    test_argv = ['ctest', '--test-dir', BUILD_DIRECTORY, '--output-on-failure', '--no-tests=ignore']
    if targets:
        build_argv.extend(['--target', *targets])
    if configuration:
        build_argv.extend(['--config', configuration])
        test_argv.extend(['-C', configuration])
    return (
        VerificationCheck('cmake-configure', 'configure', tuple(argv), timeout=180),
        VerificationCheck('cmake-build', 'build', tuple(build_argv), timeout=900),
        VerificationCheck('ctest', 'test', tuple(test_argv), timeout=300),
    )
