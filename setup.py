import os
import sys


try:
    from setuptools import setup
except ImportError:
    print("WARNING: setuptools not installed. Will try using distutils instead..")
    from distutils.core import setup


command = sys.argv[-1]
if command == 'publish':
    os.system('python setup.py sdist upload')
    sys.exit()
elif command == "coverage":
    try:
        import coverage
    except:
        sys.exit("coverage.py not installed (pip install --user coverage)")
    setup_py_path = os.path.abspath(__file__)
    os.system('coverage run -m unittest discover')
    os.system('coverage html')
    os.system('open htmlcov/index.html')
    print("Done computing coverage")
    sys.exit()

long_description = ''
if command not in ['test', 'coverage']:
    long_description = open('README.rst').read()

setup(
    name='obo_parser',
    version="0.9",
    description='.obo format parser',
    long_description=long_description,
    author='Ben Weisburd',
    author_email='weisburd@broadinstitute.org',
    url='https://github.com/macarthur-lab/obo_parser',
    py_modules=['obo_parser'],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'tqdm',
    ],
    license="MIT",
    keywords='obo, bioinformatics, parser',
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],

    test_suite='tests',
)
