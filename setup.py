from setuptools import setup

if __name__ == "__main__":
    setup(
        entry_points={
            "console_scripts": {
                "carabao = carabao.cli:app",
                "moo = carabao.cli:app",
            }
        },
        package_data={
            "carabao.cli": ["*.tcss", "*.cfg"],
        },
        include_package_data=True,
    )
