import sensors.bmi270 as bmi
from machine import I2C, Pin
from time import sleep
import deepcraft_model
import array

# BMI270 returns acceleration in g; DEEPCRAFT models expect m/s².
GRAVITY_EARTH = 9.80665

# Window size: number of samples needed to fill the model's sliding window.
# Must match fixwin_initf32(_K3, <input_size>, <window>) in model.c.
WINDOW_SIZE = 100

# --- Interrupt state (shared between callback and inference loop) ---
_data_ready = False

def _data_ready_callback(event):
    """BMI270 data-ready interrupt handler — sets flag for the inference loop."""
    global _data_ready
    _data_ready = True


# =============================================================================
# 1. sensor_init()
# =============================================================================
def sensor_init():
    """
    Initialise the BMI270 IMU sensor and configure its data-ready interrupt.

    Sensor ranges are fixed to match the DEEPCRAFT model training configuration:
      - Accelerometer : ±8 g   (C ref: IMU_ACCEL_RANGE_G  = 8)
      - Gyroscope     : ±500 dps (C ref: IMU_GYRO_RANGE_DPS = 500)

    Returns:
        sensor       -- initialised BMI270 instance
        accel_buffer -- internal buffer for accelerometer samples
        gyro_buffer  -- internal buffer for gyroscope samples
    """
    i2c = I2C(scl='P0_2', sda='P0_3')
    int_pin = Pin("P1_5", mode=Pin.IN, pull=Pin.PULL_DOWN)
    int_pin.irq(handler=_data_ready_callback, trigger=Pin.IRQ_FALLING)

    sensor_config = {
        "bus": i2c,
        "accel_range": bmi.ACCEL_RANGE_8G,
        "gyro_range":  bmi.GYRO_RANGE_500,
        "buffer_size": 6,
        "interrupt_config": int_pin,
    }

    sensor = bmi.BMI270(config=sensor_config)
    sensor.init()
    sensor.configure_data_ready_interrupt()
    print("Sensor initialised successfully!\n")

    accel_buffer, gyro_buffer = sensor.get_buffer()
    return sensor, accel_buffer, gyro_buffer


# =============================================================================
# 2. initialize_model()
# =============================================================================
def initialize_model():
    """
    Instantiate and initialise the DEEPCRAFT model.

    Returns:
        model      -- initialised DEEPCRAFT model instance
        input_dim  -- number of input features per sample (e.g. 6 for accel+gyro)
        output_dim -- number of output classes
    """
    print("Initialising DEEPCRAFT model...")
    model = deepcraft_model.DEEPCRAFT()
    model.init()

    input_dim  = model.get_model_input_dim()
    output_dim = model.get_model_output_dim()

    print(f"Model initialised successfully!")
    print(f"  -> Input  dimensions : {input_dim}")
    print(f"  -> Output dimensions : {output_dim}\n")

    return model, input_dim, output_dim


# =============================================================================
# 3. create_buffers()
# =============================================================================
def create_buffers(input_dim, output_dim):
    """
    Allocate the enqueue and dequeue float buffers for the model.

    Both buffers use array.array('f') so their raw memory can be passed
    directly to the C model via the buffer protocol, bypassing MicroPython's
    object layer entirely.

    Args:
        input_dim  -- number of input features (from initialize_model)
        output_dim -- number of output classes  (from initialize_model)

    Returns:
        enqueue_buffer -- array.array('f') of length input_dim  (sensor → model)
        output_buffer  -- array.array('f') of length output_dim (model → app)
    """
    enqueue_buffer = array.array('f', [0.0] * input_dim)
    output_buffer  = array.array('f', [0.0] * output_dim)
    print(f"Buffers created  ->  input: {input_dim} floats  |  output: {output_dim} floats\n")
    return enqueue_buffer, output_buffer


# =============================================================================
# 4. run_inference()
# =============================================================================
def run_inference(model, sensor, accel_buffer, gyro_buffer,
                  enqueue_buffer, output_buffer, input_dim, output_dim,
                  class_labels):
    """
    Main inference loop: acquire sensor data, enqueue into the model, and
    print classified predictions.

    Workflow:
      Phase 1 — Fill the sliding window (WINDOW_SIZE samples) before inferring.
      Phase 2 — Call dequeue every sample; a new prediction is produced every
                 10 enqueues (stride configured in model.c: fixwin stride = 10).

    Args:
        model          -- initialised DEEPCRAFT model (from initialize_model)
        sensor         -- initialised BMI270 instance  (from sensor_init)
        accel_buffer   -- Buffer for accelerometer  (from sensor_init)
        gyro_buffer    -- Buffer for gyroscope       (from sensor_init)
        enqueue_buffer -- float input buffer             (from create_buffers)
        output_buffer  -- float output buffer            (from create_buffers)
        input_dim      -- number of input features       (from initialize_model)
        output_dim     -- number of output classes       (from initialize_model)
        class_labels   -- list of class name strings, ordered to match model output
    """
    global _data_ready

    sample_count     = 0
    prediction_count = 0

    print(f"Phase 1: Filling sliding window ({WINDOW_SIZE} samples)...\n")

    try:
        while True:
            # Wait for the BMI270 data-ready interrupt
            if not _data_ready:
                sleep(0.001)
                continue

            # --- Read one sample from the sensor ---
            acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z = sensor.read_samples(accel_buffer, gyro_buffer)
            _data_ready = False
            sample_count += 1

            # Convert accelerometer g → m/s² (model trained on m/s²)
            # Gyroscope is already in dps — no conversion needed
            enqueue_buffer[0] = acc_x * GRAVITY_EARTH
            enqueue_buffer[1] = acc_y * GRAVITY_EARTH
            enqueue_buffer[2] = acc_z * GRAVITY_EARTH
            enqueue_buffer[3] = gyro_x
            enqueue_buffer[4] = gyro_y
            enqueue_buffer[5] = gyro_z

            # --- Enqueue sample into the model's sliding window ---
            model.enqueue(enqueue_buffer)

            # Phase 1: keep filling until the window is full
            if sample_count < WINDOW_SIZE:
                continue

            if sample_count == WINDOW_SIZE:
                print("Phase 2: Window full — starting inference...\n")

            # --- Dequeue: runs inference when stride is complete ---
            result = model.dequeue(output_buffer)

            if result == 0:
                prediction_count += 1

                # Find the highest-confidence class
                max_idx = 0
                max_val = output_buffer[0]
                for i in range(1, output_dim):
                    if output_buffer[i] > max_val:
                        max_val = output_buffer[i]
                        max_idx = i

                predicted_class = class_labels[max_idx]
                scores = "  ".join(
                    f"{class_labels[i]}: {output_buffer[i]:.4f}"
                    for i in range(output_dim)
                )
                print(f"[{sample_count}] {predicted_class.upper():<12} ({max_val:.4f}) | {scores}")

            elif result == -2:
                print(f"ERROR: Memory allocation error at sample {sample_count}")
                break
            # result == -1: stride not yet complete — silently continue

    except KeyboardInterrupt:
        print(f"\nStopped.  Samples collected: {sample_count}  |  Predictions made: {prediction_count}")


# =============================================================================
# Entry point
# =============================================================================
def main():
    # ---- User-configurable: update class labels to match your model ----
    class_labels = ["unlabelled", "circle", "shaking"]

    sensor, accel_buffer, gyro_buffer  = sensor_init()
    model, input_dim, output_dim       = initialize_model()
    enqueue_buffer, output_buffer      = create_buffers(input_dim, output_dim)

    run_inference(model, sensor, accel_buffer, gyro_buffer,
                  enqueue_buffer, output_buffer, input_dim, output_dim,
                  class_labels)

if __name__ == "__main__":
    main()