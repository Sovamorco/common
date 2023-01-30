from distutils.core import setup
from json import load

with open('requirements.json', 'r') as rf:
    reqs = load(rf)
requirements = reqs.pop('')
extras = reqs

setup(
    name='SovamorcoCommon',
    version='0.1.0',
    description='Common utils',
    author='Sovamorco',
    author_email='sovamorco@sovamor.co',
    url='https://github.com/Sovamorco/common',
    packages=['common'],
    install_requires=requirements,
    extras_require=extras,
)
