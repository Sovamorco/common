from distutils.core import setup

with open('requirements.txt', 'r') as rf:
    # .readlines() does not strip newlines
    requirements = rf.read().splitlines()

setup(
    name='SovamorcoCommon',
    version='0.0.4',
    description='Common utils',
    author='Sovamorco',
    author_email='sovamorco@sovamor.co',
    url='https://github.com/Sovamorco/common',
    packages=['common'],
    install_requires=requirements,
)
