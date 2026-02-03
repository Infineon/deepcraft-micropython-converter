# DEEPCRAFT™ MicroPython Converter

## Overview

This utility automates the conversion of [DEEPCRAFT™ Studio](https://www.infineon.com/design-resources/embedded-software/deepcraft-edge-ai-solutions/deepcraft-studio) model exports into .mpy modules compatible with MicroPython projects. It simplifies integration of AI/ML models into MicroPython applications running on platforms like Infineon’s [PSOC™ 6](https://www.infineon.com/evaluation-board/CY8CKIT-062S2-AI).

## Getting Started

### Requirements

1. [Python](https://www.python.org/) 3.12.0 or higher and [pip](https://pip.pypa.io/en/stable/).

2. A compatible DEEPCRAFT™ model (C source files and headers) generated from [DEEPCRAFT™ Studio](https://www.infineon.com/design-resources/embedded-software/deepcraft-edge-ai-solutions/deepcraft-studio).

3. [GnuWin32 Make](https://gnuwin32.sourceforge.net/downlinks/make.php).

### Preparation

Before using the converter, you need to have a DEEPCRAFT™ model generated from DEEPCRAFT™ Studio. Follow the instructions in the [DEEPCRAFT™ Studio documentation](https://developer.imagimob.com/deepcraft-studio/model-training/generating-model) to create and export your model.

### Installation and Usage

1. Open the command line and navigate to the directory where you want to install the converter.

2. Install the model conversion script by executing the following command:

    pip install git+https://github.com/Infineon/deepcraft-micropython-converter.git --target .

3. Once installed, you can run the converter using:

    python deepcraft_micropython_converter.py

4. Follow the on-screen prompts to provide the path to your DEEPCRAFT™ model files and specify any additional options as needed.

### Deploying the .mpy Model

After the script successfully ran through and converted the model it will show:
    "GEN deepcraft_model.mpy"
    [INFO] Makefile executed successfully.
    
Now you can locate the file `deepcraft_model.mpy` in the project folder and (upload it)[https://ifx-micropython.readthedocs.io/en/latest/psoc6/mpy-usage.html#the-micropython-filesystem] to your edge device running MicroPython.

### Using the Model in MicroPython

After uploading the `.mpy` file to your MicroPython device, you can import your model by executing:
    import deepcraft_model

Below is a list of supported APIs exposed by the compiled `.mpy` module. Use these functions to interact with your model instance for initialization, data input, and inference.


| Function                  | Description                                           | Input Arguments                                           | Return                                  | Sample Usage                                     |
|---------------------------|-------------------------------------------------------|------------------------------------------------------------|------------------------------------------|--------------------------------------------------|
| `DEEPCRAFT()`             | Creates an instance for your model                    | None                                                       | `deepcraft` object                       | `import deepcraft_model as m`<br>`model = m.DEEPCRAFT()` |
| `init()`                  | Initializes the model                                 | None                                                       | None                                     | `model.init()`                                   |
| `get_model_input_dim()`   | Returns expected number of sensor values per inference| None                                                       | `int`                                    | `model.get_model_input_dim()`                    |
| `get_model_output_dim()`  | Returns number of output classes                      | None                                                       | `int`                                    | `model.get_model_output_dim()`                   |
| `enqueue(data)`           | Inputs sensor data to the model                       | `<list>` of size `get_model_input_dim()`                   | `0`: Success<br> `-1`: Error          | `model.enqueue([0.0, 0.1, ...])`                 |
| `dequeue(result)`         | Outputs classification result as class probabilities  | `<list>` of size `get_model_output_dim()`  | `0`: Success<br> `-1`: Error<br> `-2`: Internal memory allocation error          | `model.dequeue([0.0, 0.0, ...])`                 |


## Other Resources 

Installation instructions and other details around DEEPCRAFT™ Studio can be found [here](https://developer.imagimob.com/deepcraft-studio).