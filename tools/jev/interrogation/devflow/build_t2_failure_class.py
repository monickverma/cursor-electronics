"""T2 failure_class: 50 pytest failure outputs shaped on real tests in phase2-stage0 (p2/tests).

Labels by construction (rule fixed before any Jev call; the class is decided by what the text shows):
  infra_hiccup            an environment exception appears in the traceback or its chain
                          (missing executable, connection refused / cannot connect, TimeoutExpired or a test timeout,
                          PermissionError or no space on a temp file, DNS/connect error)
  accuracy_disagreement   no environment exception; an assertion compares a numeric result with an expected value,
                          bound or tolerance and finds it outside (or, for a negative control, inside)
  test_nondeterminism_bug the text shows order dependence, state leaked from another test, an unseeded random draw,
                          or hash/set iteration order
  unknown                 none of the above can be read from the text (bare assert, missing key or empty result with
                          no cause, crash without detail) or an ordinary code bug that fits no class
`hard` marks items built to confuse a surface reader (e.g. an accuracy message containing 'ngspice' or seconds,
a nondeterminism failure that surfaces as a numeric approx mismatch or a database error).
No credentials, DSNs with passwords, e-mail addresses or keys appear in any item.
"""
import re

from common import SETS, secret_findings, write_jsonl

ACCURACY_FILES = ("test_simulation_accuracy.py", "test_envelope_grid.py", "test_proof_oracle.py")


def tb(nodeid, body, summary):
    title = nodeid.split("::", 1)[1].replace("::", ".")
    return (f"{'_' * 20} {title} {'_' * 20}\n\n{body.strip()}\n"
            f"{'=' * 25} short test summary info {'=' * 25}\nFAILED {nodeid} - {summary}")


ITEMS = []


def add(iid, label, nodeid, body, summary, sub, hard=False):
    ITEMS.append({"task": "T2", "item_id": f"T2-{iid}", "label": label, "subtype": sub, "hard": hard,
                  "test_file": nodeid.split("::")[0],
                  "in_accuracy_file": nodeid.split("::")[0].endswith(ACCURACY_FILES),
                  "state": {"failure": tb(nodeid, body, summary)}})


# ================================================================== infra_hiccup (14)
add("I01", "infra_hiccup", "tests/test_simulation.py::TestNgspiceIntegration::test_rc_filter_ac_sweep_passes", r"""
tests/test_simulation.py:236: in test_rc_filter_ac_sweep_passes
    result = _run(ir_rc_filter)
tests/test_simulation.py:128: in _run
    raw = NgspiceRunner()._run_sync(netlist)
backend/simulation/runner.py:96: in _run_sync
    proc = subprocess.run([_NGSPICE_CMD, "-b", "-o", str(out_path), str(cir_path)],
/usr/lib/python3.11/subprocess.py:548: in run
    with Popen(*popenargs, **kwargs) as process:
/usr/lib/python3.11/subprocess.py:1901: in _execute_child
    raise child_exception_type(errno_num, err_msg, err_filename)
E   FileNotFoundError: [Errno 2] No such file or directory: 'ngspice'
""", "FileNotFoundError: [Errno 2] No such file or directory: 'ngspice'", "missing_binary")
add("I02", "infra_hiccup", "tests/test_waveforms.py::TestFromRealRuns::test_the_rc_filter_ac_sweep_rolls_off", r"""
tests/test_waveforms.py:141: in test_the_rc_filter_ac_sweep_rolls_off
    parsed = _simulate(RC_NETLIST)
tests/test_waveforms.py:37: in _simulate
    raw = NgspiceRunner()._run_sync(netlist)
backend/simulation/runner.py:96: in _run_sync
    proc = subprocess.run([_NGSPICE_CMD, "-b", "-o", str(out_path), str(cir_path)],
/usr/lib/python3.11/subprocess.py:1901: in _execute_child
    raise child_exception_type(errno_num, err_msg, err_filename)
E   FileNotFoundError: [Errno 2] No such file or directory: 'ngspice'
""", "FileNotFoundError: [Errno 2] No such file or directory: 'ngspice'", "missing_binary")
add("I03", "infra_hiccup", "tests/test_multi_target.py::TestTheUnoIsUnchanged::test_naming_the_uno_builds_the_default_design", r"""
tests/test_multi_target.py:212: in test_naming_the_uno_builds_the_default_design
    build = compile_project(project, timeout_s=600)
backend/generators/firmware/compile_gate.py:88: in compile_project
    proc = subprocess.run(["pio", "run", "-d", str(workdir), "-e", env],
/usr/lib/python3.11/subprocess.py:1901: in _execute_child
    raise child_exception_type(errno_num, err_msg, err_filename)
E   FileNotFoundError: [Errno 2] No such file or directory: 'pio'
""", "FileNotFoundError: [Errno 2] No such file or directory: 'pio'", "missing_binary")
add("I04", "infra_hiccup", "tests/test_postgres_signoff.py::TestSignOffOnPostgres::test_the_signature_is_stored_and_survives_a_restart", r"""
tests/test_postgres_signoff.py:135: in env
    user, ir = _run(_seed(_intent()))
tests/test_postgres_signoff.py:71: in _seed
    async with engine.begin() as conn:
.venv/lib/python3.11/site-packages/sqlalchemy/ext/asyncio/engine.py:1066: in begin
    async with conn:
.venv/lib/python3.11/site-packages/asyncpg/connect_utils.py:1049: in _create_ssl_connection
    tr, pr = await loop.create_connection(
/usr/lib/python3.11/asyncio/base_events.py:1085: in create_connection
    raise exceptions[0]
E   ConnectionRefusedError: [Errno 111] Connect call failed ('127.0.0.1', 5432)
""", "ConnectionRefusedError: [Errno 111] Connect call failed ('127.0.0.1', 5432)", "db_refused")
add("I05", "infra_hiccup", "tests/test_migrations.py::TestFailureNeverStopsTheApp::test_all_statements_run_in_order_when_it_is_up", r"""
tests/test_migrations.py:188: in test_all_statements_run_in_order_when_it_is_up
    applied = _run(run_migrations(engine))
backend/db/migrations.py:61: in run_migrations
    async with engine.begin() as conn:
.venv/lib/python3.11/site-packages/asyncpg/connect_utils.py:1102: in __connect_addr
    raise OSError(msg)
E   OSError: Multiple exceptions: [Errno 111] Connect call failed ('::1', 5432, 0, 0), [Errno 111] Connect call failed ('127.0.0.1', 5432)
""", "OSError: Multiple exceptions: [Errno 111] Connect call failed ('::1', 5432, 0, 0), ...", "db_refused")
add("I06", "infra_hiccup", "tests/test_postgres_signoff.py::TestTheConditionalUpdateOnPostgres::test_a_stale_version_writes_nothing", r"""
tests/test_postgres_signoff.py:201: in test_a_stale_version_writes_nothing
    stored = _run(_load(circuit_id))
tests/test_postgres_signoff.py:88: in _load
    async with session_factory() as s:
.venv/lib/python3.11/site-packages/asyncpg/connection.py:2329: in connect
    return await connect_utils._connect(
E   asyncpg.exceptions.CannotConnectNowError: the database system is starting up
""", "asyncpg.exceptions.CannotConnectNowError: the database system is starting up", "db_refused")
add("I07", "infra_hiccup", "tests/test_simulation_accuracy.py::TestRCLowPassAccuracy::test_magnitude_matches_closed_form_across_sweep[68k-2n2]", r"""
tests/test_simulation_accuracy.py:273: in test_magnitude_matches_closed_form_across_sweep
    points = run_ir(ir).ac_points
tests/test_simulation_accuracy.py:151: in run_ir
    raw = NgspiceRunner()._run_sync(netlist)
backend/simulation/runner.py:96: in _run_sync
    proc = subprocess.run([_NGSPICE_CMD, "-b", "-o", str(out_path), str(cir_path)],
/usr/lib/python3.11/subprocess.py:550: in run
    stdout, stderr = process.communicate(input, timeout=timeout)
/usr/lib/python3.11/subprocess.py:1209: in _check_timeout
    raise TimeoutExpired(
E   subprocess.TimeoutExpired: Command '['ngspice', '-b', '-o', '/tmp/tmpq8v2x1.log', '/tmp/tmpq8v2x1.cir']' timed out after 30 seconds
""", "subprocess.TimeoutExpired: Command '['ngspice', '-b', ...]' timed out after 30 seconds", "timeout", hard=True)
add("I08", "infra_hiccup", "tests/test_multi_target.py::TestTheFirmwareDrivesTheDesignsPins::test_every_pin_define_is_the_pin_wired_to_its_net", r"""
tests/test_multi_target.py:266: in test_every_pin_define_is_the_pin_wired_to_its_net
    build = compile_project(project, timeout_s=600)
backend/generators/firmware/compile_gate.py:88: in compile_project
    proc = subprocess.run(["pio", "run", "-d", str(workdir), "-e", env],
/usr/lib/python3.11/subprocess.py:1209: in _check_timeout
    raise TimeoutExpired(
E   subprocess.TimeoutExpired: Command '['pio', 'run', '-d', '/tmp/pio-esp32dev-3k1', '-e', 'esp32dev']' timed out after 600 seconds
""", "subprocess.TimeoutExpired: Command '['pio', 'run', ...]' timed out after 600 seconds", "timeout")
add("I09", "infra_hiccup", "tests/test_firmware_gate.py::TestTheGateNeverShowsUnbuiltSource::test_a_new_project_is_queued_and_its_source_withheld", r"""
tests/test_firmware_gate.py:143: in test_a_new_project_is_queued_and_its_source_withheld
    view = _run(firmware_view(db, ir))
backend/api/routes/firmware.py:118: in firmware_view
    build_firmware.apply_async(args=[ir.circuit_id, project_hash], task_id=job_id)
.venv/lib/python3.11/site-packages/kombu/connection.py:476: in _reraise_as_library_errors
    raise ConnectionError(str(exc)) from exc
E   kombu.exceptions.OperationalError: [Errno 111] Connection refused
""", "kombu.exceptions.OperationalError: [Errno 111] Connection refused", "broker_refused")
add("I10", "infra_hiccup", "tests/test_request_log.py::TestRequestLogRoundTrip::test_row_survives_a_round_trip", r"""
tests/test_request_log.py:212: in test_row_survives_a_round_trip
    limiter.hit("10/hour", key)
.venv/lib/python3.11/site-packages/limits/storage/redis.py:143: in incr
    return self.lua_incr_expire([key], [expiry, amount])
.venv/lib/python3.11/site-packages/redis/connection.py:707: in connect
    raise ConnectionError(self._error_message(e))
E   redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379. Connection refused.
""", "redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379. Connection refused.", "broker_refused")
add("I11", "infra_hiccup", "tests/test_simulation.py::TestNgspiceIntegration::test_voltage_divider_dc_op_passes", r"""
tests/test_simulation.py:231: in test_voltage_divider_dc_op_passes
    result = _run(ir_voltage_divider)
backend/simulation/runner.py:118: in _run_sync
    os.unlink(cir_path)
E   PermissionError: [WinError 32] The process cannot access the file because it is being used by another process: 'C:\\Users\\<user>\\AppData\\Local\\Temp\\tmp7h2k9d.cir'
""", "PermissionError: [WinError 32] The process cannot access the file because it is being used by another process", "tempfile")
add("I12", "infra_hiccup", "tests/test_proof_oracle.py::test_every_counterexample_is_a_real_violation[voltage_divider-vout]", r"""
tests/test_proof_oracle.py:171: in test_every_counterexample_is_a_real_violation
    out = _ngspice(netlist)
tests/test_proof_oracle.py:61: in _ngspice
    with tempfile.NamedTemporaryFile("w", suffix=".cir", delete=False) as f:
/usr/lib/python3.11/tempfile.py:483: in func_wrapper
    return func(*args, **kwargs)
E   OSError: [Errno 28] No space left on device
""", "OSError: [Errno 28] No space left on device", "tempfile", hard=True)
add("I13", "infra_hiccup", "tests/test_live_llm_paths.py::test_a_plain_request_reaches_its_generator_and_is_proved", r"""
tests/test_live_llm_paths.py:54: in test_a_plain_request_reaches_its_generator_and_is_proved
    intent = producer.produce("RC low-pass at 1 kHz from a 5 V rail")
backend/ai/intent_producer.py:142: in produce
    response = self.client.messages.create(**kwargs)
backend/ai/openai_compat.py:77: in create
    r = self._http.post(self._url, json=body, timeout=self._timeout)
.venv/lib/python3.11/site-packages/httpx/_transports/default.py:86: in map_httpcore_exceptions
    raise mapped_exc(message) from exc
E   httpx.ConnectError: [Errno -3] Temporary failure in name resolution
""", "httpx.ConnectError: [Errno -3] Temporary failure in name resolution", "network")
add("I14", "infra_hiccup", "tests/test_proof_oracle.py::test_every_corner_of_the_proven_box_is_inside_the_bounds[rs485_node-idle_bias]", r"""
tests/test_proof_oracle.py:152: in test_every_corner_of_the_proven_box_is_inside_the_bounds
    out = _ngspice(netlist)
tests/test_proof_oracle.py:66: in _ngspice
    proc.wait()
/usr/lib/python3.11/subprocess.py:2046: in _wait
    (pid, sts) = self._try_wait(0)
E   Failed: Timeout >300.0s

+++++++++++++++++++++++++++++++++++ Timeout ++++++++++++++++++++++++++++++++++++
~~~~~~~~~~~~~~~~ Stack of <unknown> (140231177082688) ~~~~~~~~~~~~~~~~
  File "/usr/lib/python3.11/subprocess.py", line 2008, in _try_wait
    (pid, sts) = os.waitpid(self.pid, wait_flags)
""", "Failed: Timeout >300.0s", "timeout", hard=True)

# ================================================================== accuracy_disagreement (16)
add("A01", "accuracy_disagreement", "tests/test_simulation_accuracy.py::TestRCLowPassAccuracy::test_cutoff_frequency_matches_closed_form[1k59-100n]", r"""
self = <tests.test_simulation_accuracy.TestRCLowPassAccuracy object at 0x7f3a2c1b9d50>, r_value = '1k59', c_value = '100n'

        err = abs(measured - f_c) / f_c
>       assert err <= TOLERANCE, (
            f"R={r_value} C={c_value}: measured cutoff {measured:.2f}Hz vs "
            f"closed-form {f_c:.2f}Hz — {err * 100:.3f}% off"
        )
E       AssertionError: R=1k59 C=100n: measured cutoff 1034.12Hz vs closed-form 1000.97Hz — 3.312% off
E       assert 0.03311817 <= 0.02

tests/test_simulation_accuracy.py:310: AssertionError
""", "AssertionError: R=1k59 C=100n: measured cutoff 1034.12Hz vs closed-form 1000.97Hz — 3.312% off", "tolerance")
add("A02", "accuracy_disagreement", "tests/test_simulation_accuracy.py::TestRCLowPassAccuracy::test_magnitude_matches_closed_form_across_sweep[3k4-47n]", r"""
        assert checked >= 80, f"Expected a dense sweep, only got {checked} points"
>       assert worst_err <= TOLERANCE, (
            f"R={r_value} C={c_value} (f_c={f_c:.2f}Hz): worst deviation "
            f"{worst_err * 100:.3f}% at {worst_f:.2f}Hz exceeds the "
            f"{TOLERANCE * 100:.0f}% analytical gate. This is a netlist "
            f"generator bug, not measurement noise."
        )
E       AssertionError: R=3k4 C=47n (f_c=995.95Hz): worst deviation 2.874% at 15848.93Hz exceeds the 2% analytical gate. This is a netlist generator bug, not measurement noise.
E       assert 0.02874 <= 0.02

tests/test_simulation_accuracy.py:288: AssertionError
""", "AssertionError: R=3k4 C=47n (f_c=995.95Hz): worst deviation 2.874% at 15848.93Hz exceeds the 2% analytical gate", "tolerance")
add("A03", "accuracy_disagreement", "tests/test_simulation_accuracy.py::TestVoltageDividerAccuracy::test_dc_output_matches_closed_form[12.0-7k-5k1]", r"""
        measured = data.dc_voltages["vout"]
        err = abs(measured - expected) / expected
>       assert err <= TOLERANCE, (
            f"{vin}V through {r_top}/{r_bottom}: ngspice {measured:.6f}V vs "
            f"closed-form {expected:.6f}V — {err * 100:.3f}% off"
        )
E       AssertionError: 12.0V through 7k/5k1: ngspice 5.214000V vs closed-form 5.066667V — 2.908% off
E       assert 0.02907894 <= 0.02

tests/test_simulation_accuracy.py:354: AssertionError
""", "AssertionError: 12.0V through 7k/5k1: ngspice 5.214000V vs closed-form 5.066667V — 2.908% off", "tolerance", hard=True)
add("A04", "accuracy_disagreement", "tests/test_simulation_accuracy.py::TestRCLowPassAccuracy::test_magnitude_at_cutoff_is_minus_3db", r"""
        measured = values["out"]
        assert measured == pytest.approx(VIN / math.sqrt(2.0), rel=TOLERANCE)

        db = 20.0 * math.log10(measured / VIN)
>       assert db == pytest.approx(-3.01, abs=0.05), f"Got {db:.4f} dB at cutoff"
E       AssertionError: Got -3.0712 dB at cutoff
E       assert -3.0712 == -3.01 ± 5.0e-02

tests/test_simulation_accuracy.py:336: AssertionError
""", "AssertionError: Got -3.0712 dB at cutoff", "tolerance")
add("A05", "accuracy_disagreement", "tests/test_envelope_grid.py::TestTheGridOnRealNgspice::test_clean_grid_passes_within_two_percent", r"""
        report = run_grid(RcLowpassGenerator(), runner=NgspiceRunner())
>       assert report.passed, report.summary()
E       AssertionError: grid gate FAILED for rc_lowpass@0.2.3: 3 of 27 points exceed 2.0%
E         cutoff_hz=5000 supply_v=3.3  predict 5000.0 Hz  ngspice 5163.9 Hz  error 3.28%
E         cutoff_hz=5000 supply_v=5.0  predict 5000.0 Hz  ngspice 5161.2 Hz  error 3.22%
E         cutoff_hz=5000 supply_v=12   predict 5000.0 Hz  ngspice 5158.8 Hz  error 3.18%
E       assert False
E        +  where False = <GridReport rc_lowpass@0.2.3 points=27 failures=3>.passed

tests/test_envelope_grid.py:286: AssertionError
""", "AssertionError: grid gate FAILED for rc_lowpass@0.2.3: 3 of 27 points exceed 2.0%", "tolerance", hard=True)
add("A06", "accuracy_disagreement", "tests/test_envelope_grid.py::TestTheGridOnRealNgspice::test_worst_deviation_is_print_precision", r"""
        report = run_grid(RcLowpassGenerator(), runner=NgspiceRunner())
>       assert report.worst_error < 1e-4, (
            f"worst deviation {report.worst_error:.2e} is not print precision"
        )
E       AssertionError: worst deviation 4.12e-02 is not print precision
E       assert 0.0412 < 0.0001

tests/test_envelope_grid.py:293: AssertionError
""", "AssertionError: worst deviation 4.12e-02 is not print precision", "tolerance")
add("A07", "accuracy_disagreement", "tests/test_proof_oracle.py::test_every_corner_of_the_proven_box_is_inside_the_bounds[rc_lowpass-cutoff]", r"""
        for corner in corners(spec.box):
            value = _measure(circuit, corner, spec.quantity)
>           assert lo * (1 - 1e-7) <= value <= hi * (1 + 1e-7), \
                f"corner {corner}: ngspice {spec.quantity}={value:.6g} outside proven bounds [{lo:.6g}, {hi:.6g}]"
E           AssertionError: corner {'R1': 3434.0, 'C1': 4.23e-08}: ngspice f_c=1129.1 outside proven bounds [896.4, 1120.2]
E           assert 1129.1 <= (1120.2 * (1 + 1e-07))

tests/test_proof_oracle.py:159: AssertionError
""", "AssertionError: corner {'R1': 3434.0, 'C1': 4.23e-08}: ngspice f_c=1129.1 outside proven bounds [896.4, 1120.2]", "bound")
add("A08", "accuracy_disagreement", "tests/test_simulation.py::TestSimulationGrader::test_ac_grading_at_cutoff_frequency_passes", r"""
        result = SimulationGrader().grade(ir_rc_filter, parsed)
>       assert result.passed, result.checks
E       AssertionError: [Check(node='out', frequency_hz=1000.0, expected=3.5355, actual=2.9102, error=0.1769, tolerance=0.15, passed=False)]
E       assert False
E        +  where False = GradeResult(passed=False, checks=[...]).passed

tests/test_simulation.py:207: AssertionError
""", "AssertionError: [Check(node='out', frequency_hz=1000.0, expected=3.5355, actual=2.9102, error=0.1769, ...)]", "tolerance")
add("A09", "accuracy_disagreement", "tests/test_simulation.py::TestSpiceResultParser::test_parse_dc_op_extracts_vout_voltage", r"""
    def test_parse_dc_op_extracts_vout_voltage(self):
        data = SpiceResultParser().parse(DC_STDOUT, "")
>       assert data.dc_voltages["vout_5v"] == pytest.approx(5.07, rel=0.001)
E       assert 5.2 == 5.07 ± 5.1e-03
E         comparison failed
E         Obtained: 5.2
E         Expected: 5.07 ± 5.1e-03

tests/test_simulation.py:150: AssertionError
""", "assert 5.2 == 5.07 ± 5.1e-03", "approx")
add("A10", "accuracy_disagreement", "tests/test_generator_library.py::TestEveryGridPoint::test_every_band_contains_its_nominal[led_indicator-uno-10mA]", r"""
        band = generator.predict(intent)["led_current_a"]
>       assert band.lo <= band.nominal <= band.hi, (
            f"{generator.name}@{generator.version}: nominal {band.nominal*1e3:.2f} mA outside "
            f"band [{band.lo*1e3:.2f}, {band.hi*1e3:.2f}] mA"
        )
E       AssertionError: led_indicator@0.2.0: nominal 11.62 mA outside band [8.19, 11.40] mA
E       assert 0.01162 <= 0.0114

tests/test_generator_library.py:233: AssertionError
""", "AssertionError: led_indicator@0.2.0: nominal 11.62 mA outside band [8.19, 11.40] mA", "bound")
add("A11", "accuracy_disagreement", "tests/test_proof.py::TestDividerProperties::test_the_vout_bounds_hold_at_every_corner", r"""
        for corner in _corners(box):
            v = _vout(corner)
>           assert lo <= v <= hi, f"VOUT {v:.4f} V at {corner} outside proven band [{lo:.2f}, {hi:.2f}] V"
E           AssertionError: VOUT 3.3521 V at {'R1': 3366.0, 'R2': 6716.5} outside proven band [3.28, 3.34] V
E           assert 3.3521 <= 3.34

tests/test_proof.py:412: AssertionError
""", "AssertionError: VOUT 3.3521 V at {'R1': 3366.0, 'R2': 6716.5} outside proven band [3.28, 3.34] V", "bound")
add("A12", "accuracy_disagreement", "tests/test_multi_target.py::TestTheBoardIsPhysics::test_the_same_led_current_needs_a_smaller_resistor_on_3v3", r"""
        ir = realize(intent_for("blackpill_f411ce", led_ma=13)).circuit
        i_pin = _pin_current(ir)
>       assert i_pin <= target.pin_rating_a, (
            f"pin current {i_pin*1e3:.2f} mA exceeds {target.pin_rating_a*1e3:.1f} mA rating "
            f"({(i_pin/target.pin_rating_a - 1)*100:.1f}% over)"
        )
E       AssertionError: pin current 13.40 mA exceeds 13.0 mA rating (3.1% over)
E       assert 0.0134 <= 0.013

tests/test_multi_target.py:98: AssertionError
""", "AssertionError: pin current 13.40 mA exceeds 13.0 mA rating (3.1% over)", "bound")
add("A13", "accuracy_disagreement", "tests/test_waveforms.py::TestFromRealRuns::test_the_rc_filter_ac_sweep_rolls_off", r"""
        at_fc = _nearest(w["ac"]["points"], f_c)
>       assert at_fc["out"] == pytest.approx(VIN / math.sqrt(2.0), rel=1e-3)
E       assert 3.61 == 3.535534 ± 3.5e-03
E         comparison failed
E         Obtained: 3.61
E         Expected: 3.535534 ± 3.5e-03

tests/test_waveforms.py:149: AssertionError
""", "assert 3.61 == 3.535534 ± 3.5e-03", "approx")
add("A14", "accuracy_disagreement", "tests/test_simulation_accuracy.py::TestHarnessRejectsWrongValues::test_wrong_capacitor_decade_is_caught", r"""
        worst = max(
            abs(v["out"] - rc_lowpass_magnitude(VIN, f, f_c_claimed))
            / rc_lowpass_magnitude(VIN, f, f_c_claimed)
            for f, v in points if "out" in v
        )
>       assert worst > TOLERANCE, (
            "A capacitor wrong by a decade slipped through the analytical gate — "
            "the gate is not measuring what it claims to measure."
        )
E       AssertionError: A capacitor wrong by a decade slipped through the analytical gate — the gate is not measuring what it claims to measure.
E       assert 0.0121 > 0.02

tests/test_simulation_accuracy.py:381: AssertionError
""", "AssertionError: A capacitor wrong by a decade slipped through the analytical gate", "negative_control", hard=True)
add("A15", "accuracy_disagreement", "tests/test_envelope_grid.py::TestTheGridOnRealNgspice::test_clean_grid_passes_within_two_percent[dht22_node]", r"""
        report = run_grid(Dht22NodeGenerator(), runner=NgspiceRunner())
>       assert report.passed, report.summary()
E       AssertionError: grid gate FAILED for dht22_node@0.2.0 after 29.8 s of ngspice runs: 1 of 12 points exceeds 2.0%
E         supply_v=3.3 pullup=4k7  predict data_idle 3.300 V  ngspice 3.212 V  error 2.67%
E       assert False

tests/test_envelope_grid.py:286: AssertionError
""", "AssertionError: grid gate FAILED for dht22_node@0.2.0 after 29.8 s of ngspice runs: 1 of 12 points exceeds 2.0%", "tolerance", hard=True)
add("A16", "accuracy_disagreement", "tests/test_rc_lowpass_generator.py::TestClosedForm::test_cutoff_matches_the_shipping_reference_design", r"""
        design = RcLowpassGenerator().generate(reference_intent())
        f_c = cutoff_hz(design)
>       assert f_c == pytest.approx(1000.0, rel=0.005), f"reference cutoff {f_c:.2f} Hz"
E       AssertionError: reference cutoff 1012.61 Hz
E       assert 1012.61 == 1000.0 ± 5.0e+00

tests/test_rc_lowpass_generator.py:77: AssertionError
""", "AssertionError: reference cutoff 1012.61 Hz", "approx")

# ================================================================== test_nondeterminism_bug (10)
add("N01", "test_nondeterminism_bug", "tests/test_registry.py::TestCatalogue::test_default_registry_installs_the_real_generator", r"""
Using --randomly-seed=3141592
        reg = default_registry()
>       assert sorted(g.name for g in reg) == FIVE
E       AssertionError: assert ['dht22_node', 'led_indicator', 'rc_lowpass', 'rs485_node', 'toy_generator', 'voltage_divider'] == ['dht22_node', 'led_indicator', 'rc_lowpass', 'rs485_node', 'voltage_divider']
E         At index 4 diff: 'toy_generator' != 'voltage_divider'
E         Left contains one more item: 'voltage_divider'

tests/test_registry.py:118: AssertionError
----------------------------- Captured log call ------------------------------
INFO generators.registry: registered toy_generator (from tests/test_registry.py::TestRegistration::test_registers_a_conforming_generator, earlier in this session)
""", "AssertionError: assert [... 'toy_generator' ...] == [...]", "order_dependent")
add("N02", "test_nondeterminism_bug", "tests/test_request_log.py::TestRequestLogRowSchemaEnforcement::test_minimal_row_is_valid", r"""
Using --randomly-seed=90210
        log_request(minimal_row())
>       assert len(_SINK) == 1
E       assert 4 == 1
E        +  where 4 = len([RequestLogRow(route='/design/generate', request_id='t-ai-01', ...), RequestLogRow(route='/design/generate', request_id='t-ai-02', ...), RequestLogRow(route='/design/patch', request_id='t-ai-03', ...), RequestLogRow(route='/design/generate', request_id='t-min-01', ...)])

tests/test_request_log.py:64: AssertionError
note: _SINK is a module-level list in observability/request_log.py; rows t-ai-01..03 were written by tests/test_ai_layer.py, which ran first under this seed and does not clear it
""", "assert 4 == 1", "shared_state")
add("N03", "test_nondeterminism_bug", "tests/test_pcb_route.py::TestPcbEngineGate::test_disabled_returns_501", r"""
        r = client.post("/pcb/compile", json=BODY, headers=auth)
>       assert r.status_code == 501
E       assert 200 == 501
E        +  where 200 = <Response [200 OK]>.status_code

tests/test_pcb_route.py:41: AssertionError
----------------------------- Captured stdout setup -----------------------------
PCB_ENGINE_ENABLED=1 (left in os.environ by tests/test_pcb_placement.py::test_placement_places_every_component, which set it directly instead of through monkeypatch)
""", "assert 200 == 501", "shared_state")
add("N04", "test_nondeterminism_bug", "tests/test_auth.py::TestRegisterRoute::test_register_creates_a_user", r"""
Using --randomly-seed=777
        r = client.post("/auth/register", json={"username": "signoff_fixture_user", "password": FIXTURE_PW})
.venv/lib/python3.11/site-packages/asyncpg/connection.py:1822: in __execute
    result, _ = await self._do_execute(
E   asyncpg.exceptions.UniqueViolationError: duplicate key value violates unique constraint "users_username_key"
E   DETAIL:  Key (username)=(signoff_fixture_user) already exists.

note: the row was inserted by tests/test_postgres_signoff.py fixture `env` in the same database, which ran earlier under this seed and never rolls back
""", "asyncpg.exceptions.UniqueViolationError: duplicate key value violates unique constraint \"users_username_key\"", "shared_state", hard=True)
add("N05", "test_nondeterminism_bug", "tests/test_intent_patch.py::TestOperations::test_replace_changes_one_requirement", r"""
Using --randomly-seed=1618
        out = apply_patch(STORE, circuit_id, base_revision=1, ops=[replace("/requirements/cutoff_hz", 2000)])
>       assert out.revision == 2
E       AssertionError: assert 4 == 2
E        +  where 4 = PatchOutcome(revision=4, conflict=False, ...).revision

tests/test_intent_patch.py:52: AssertionError
note: STORE is a session-scoped fixture shared by every test in the session; circuit_id is uuid5 of the same intent, so two earlier tests in tests/test_realize.py already appended revisions 2 and 3
""", "AssertionError: assert 4 == 2", "shared_state", hard=True)
add("N06", "test_nondeterminism_bug", "tests/test_envelope_grid.py::TestFaultInjection::test_scaled_values_stay_parseable_at_every_magnitude[R1-random]", r"""
    def test_scaled_values_stay_parseable_at_every_magnitude(self, component_id, factor):
        if factor == "random":
            factor = random.uniform(0.5, 2.0)     # no seed is set anywhere in this module
        before = _value_of(NETLIST, component_id)
        after = _value_of(scale_component(NETLIST, component_id, factor), component_id)
>       assert after == pytest.approx(before * factor, rel=1e-6)
E       assert 6800.0 == 6799.9864 ± 6.8e-03
E         comparison failed
E         Obtained: 6800.0
E         Expected: 6799.9864 ± 6.8e-03

component_id = 'R1', factor = 1.9999960021873
tests/test_envelope_grid.py:233: AssertionError
""", "assert 6800.0 == 6799.9864 ± 6.8e-03", "unseeded_random", hard=True)
add("N07", "test_nondeterminism_bug", "tests/test_claims.py::TestSampledClaims::test_a_sampled_claim_is_reproducible", r"""
        rng = np.random.default_rng()          # unseeded
        first = sample_claim(design, n=1000, rng=rng)
        second = sample_claim(design, n=1000, rng=np.random.default_rng())
>       assert first.verdict == second.verdict
E       AssertionError: assert 'holds' == 'fails'
E         - fails
E         + holds
E       first: 1000/1000 samples inside; second: 998/1000 samples inside

tests/test_claims.py:388: AssertionError
""", "AssertionError: assert 'holds' == 'fails'", "unseeded_random")
add("N08", "test_nondeterminism_bug", "tests/test_schematic_generator.py::test_every_node_gets_a_net_label", r"""
PYTHONHASHSEED=2718281828 (set by pytest-randomly for this run)
        labels = list({c.node_id for c in ir.connections})
>       assert labels == ["GND", "VCC_5V", "OUT"]
E       AssertionError: assert ['OUT', 'GND', 'VCC_5V'] == ['GND', 'VCC_5V', 'OUT']
E         At index 0 diff: 'OUT' != 'GND'

tests/test_schematic_generator.py:141: AssertionError
""", "AssertionError: assert ['OUT', 'GND', 'VCC_5V'] == ['GND', 'VCC_5V', 'OUT']", "hash_order")
add("N09", "test_nondeterminism_bug", "tests/test_abstention_corpus.py::TestAbstentionRates::test_false_acceptance_rate_is_zero", r"""
tests/test_abstention_corpus.py:19: in <module>
    random.shuffle(CORPUS)                     # module import time, unseeded
        accepted = [c for c in CORPUS[:200] if registry.dispatch(c.intent).accepted]
>       assert not [c for c in accepted if c.label == "refuse"], ...
E       AssertionError: 1 case(s) labelled refuse were accepted: ['rc_bandpass_03']
E       assert not ['rc_bandpass_03']

tests/test_abstention_corpus.py:88: AssertionError
note: CORPUS[:200] is a different slice on every run because the shuffle above is unseeded
""", "AssertionError: 1 case(s) labelled refuse were accepted: ['rc_bandpass_03']", "unseeded_random")
add("N10", "test_nondeterminism_bug", "tests/test_generator_library.py::TestLibrary::test_each_implements_claims[led_indicator]", r"""
Using --randomly-seed=4242
        intent = intent_for("led_indicator", **DEFAULTS["led_indicator"])
        band = generator.predict(intent)["led_current_a"]
>       assert band.nominal == pytest.approx(0.010, rel=0.02)
E       assert 0.02 == 0.01 ± 2.0e-04

tests/test_generator_library.py:141: AssertionError
note: DEFAULTS is a module-level dict; tests/test_multi_target.py::TestTheBoardIsPhysics::test_the_same_led_current_needs_a_smaller_resistor_on_3v3 ran earlier under this seed and set DEFAULTS['led_indicator']['led_ma'] = 20 without copying it
""", "assert 0.02 == 0.01 ± 2.0e-04", "shared_state", hard=True)

# ================================================================== unknown (10)
add("U01", "unknown", "tests/test_simulation_accuracy.py::TestRCLowPassAccuracy::test_cutoff_frequency_matches_closed_form[1k59-100n]", r"""
        ir = make_rc_lowpass_ir(r_value, c_value, f_c / 100.0, f_c * 100.0)
        points = run_ir(ir).ac_points
>       assert points, f"No AC points returned for R={r_value} C={c_value}"
E       AssertionError: No AC points returned for R=1k59 C=100n
E       assert []

tests/test_simulation_accuracy.py:270: AssertionError
""", "AssertionError: No AC points returned for R=1k59 C=100n", "empty_result", hard=True)
add("U02", "unknown", "tests/test_simulation_accuracy.py::TestRCLowPassAccuracy::test_magnitude_at_cutoff_is_minus_3db", r"""
        freq, values = points[0]
        assert freq == pytest.approx(f_c, rel=1e-6), (
            f"Expected first sample on f_c={f_c:.4f}Hz, got {freq:.4f}Hz"
        )
>       measured = values["out"]
E       KeyError: 'out'

tests/test_simulation_accuracy.py:332: KeyError
""", "KeyError: 'out'", "missing_key", hard=True)
add("U03", "unknown", "tests/test_realize.py::TestDeterminism::test_same_intent_same_version_is_byte_identical", r"""
        a = realize(intent)
        b = realize(intent)
>       assert a.ok and b.ok
E       assert (False)
E        +  where False = <RealizeResult ok=False circuit=None refusal=...>.ok

tests/test_realize.py:44: AssertionError
""", "assert (False)", "bare_assert")
add("U04", "unknown", "tests/test_proof.py::TestSeriesPower::test_the_falls_lemma_is_guarded", r"""
[gw2] node down: Not properly terminated
worker 'gw2' crashed while running 'tests/test_proof.py::TestSeriesPower::test_the_falls_lemma_is_guarded'
""", "worker 'gw2' crashed while running 'tests/test_proof.py::TestSeriesPower::test_the_falls_lemma_is_guarded'", "crash")
add("U05", "unknown", "tests/test_proof.py::TestProver::test_every_property_of_the_library_proves", r"""
Fatal Python error: Segmentation fault

Current thread 0x00007f1c8f5e4740 (most recent call first):
  File ".venv/lib/python3.11/site-packages/z3/z3core.py", line 4163 in Z3_solver_check_assumptions
  File ".venv/lib/python3.11/site-packages/z3/z3.py", line 7147 in check
  File "backend/proof/prover.py", line 212 in _decide
""", "Fatal Python error: Segmentation fault", "crash")
add("U06", "unknown", "tests/test_registry.py::TestDispatch::test_dispatches_to_the_accepting_generator", r"""
        result = reg.dispatch(intent)
>       assert result.status == "accepted"
E       AssertionError: assert 'refused' == 'accepted'
E         - accepted
E         + refused

tests/test_registry.py:151: AssertionError
""", "AssertionError: assert 'refused' == 'accepted'", "semantic_mismatch")
add("U07", "unknown", "tests/test_simulation.py::TestNgspiceIntegration::test_rc_filter_wrong_capacitor_fails", r"""
backend/simulation/grader.py:74: in _grade_ac
    error = abs(actual - expected) / abs(expected)
E   TypeError: unsupported operand type(s) for -: 'NoneType' and 'float'

tests/test_simulation.py:241: TypeError
""", "TypeError: unsupported operand type(s) for -: 'NoneType' and 'float'", "code_bug", hard=True)
add("U08", "unknown", "tests/test_live_llm_paths.py::test_a_stated_value_becomes_a_cited_operation", r"""
backend/ai/openai_compat.py:83: in create
    data = r.json()
.venv/lib/python3.11/site-packages/httpx/_models.py:764: in json
    return jsonlib.loads(self.content, **kwargs)
/usr/lib/python3.11/json/decoder.py:355: in raw_decode
    raise JSONDecodeError("Expecting value", s, err.value) from None
E   json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
""", "json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)", "code_or_upstream", hard=True)
add("U09", "unknown", "tests/test_waveforms.py::TestTransientParser::test_rows_are_read_with_every_column", r"""
backend/simulation/parser.py:141: in _parse_tran_rows
    values = [float(tok) for tok in row.split()[1:]]
E   ValueError: could not convert string to float: '1.0e+03hz'

tests/test_waveforms.py:58: ValueError
""", "ValueError: could not convert string to float: '1.0e+03hz'", "code_bug")
add("U10", "unknown", "tests/test_form_producer.py::TestProducesValidIntent::test_builds_a_valid_intent_with_zero_api_calls", r"""
backend/ai/form_producer.py:96: in produce
    return IntentIR.model_validate(payload)
E   pydantic_core._pydantic_core.ValidationError: 1 validation error for IntentIR
E   requirements.cutoff_hz
E     Input should be greater than 0 [type=greater_than, input_value=0.0, input_type=float]

tests/test_form_producer.py:121: ValidationError
""", "pydantic_core._pydantic_core.ValidationError: 1 validation error for IntentIR", "code_bug")

# ------------------------------------------------------------------ deterministic baseline (as specified in the
# earlier report: "TimeoutExpired, FileNotFoundError: ngspice, connection refused (Redis/Postgres), and
# tempfile/permission errors count as infra. An AssertionError whose message compares a numeric against a
# tolerance, or any test under test_simulation_accuracy.py/grid/proof oracle, counts as accuracy." Unmatched
# tracebacks go to Jev.)
INFRA_RX = re.compile(r"TimeoutExpired|timed out after|Failed: Timeout|FileNotFoundError: \[Errno 2\] No such file "
                      r"or directory: '(ngspice|ngspice_con|pio|platformio)'|Connection refused|Connect call failed|"
                      r"ConnectionRefusedError|CannotConnectNowError|PermissionError|No space left on device|"
                      r"httpx\.ConnectError")
NUMERIC_TOL_RX = re.compile(r"AssertionError.*(\d+(\.\d+)?\s*%|outside (proven )?(band|bounds)|exceeds)|"
                            r"assert [-\d.e]+ (<=|<|>|>=) [-\d.e(]+|assert [-\d.e]+ == [-\d.e]+ ± ")


def det_classify(text, test_file):
    if INFRA_RX.search(text):
        return "infra_hiccup"
    if "AssertionError" in text or "assert " in text:
        if NUMERIC_TOL_RX.search(text) or test_file.endswith(ACCURACY_FILES):
            return "accuracy_disagreement"
    return "unmatched"


def build():
    for it in ITEMS:
        it["det_baseline"] = {"label": det_classify(it["state"]["failure"], it["test_file"]),
                              "rule": "earlier report's deterministic spec; 'unmatched' is sent to Jev"}
        it["label_rule"] = "construction class of the text (see module docstring)"
        assert not secret_findings(it["state"]), it["item_id"]
    return ITEMS


if __name__ == "__main__":
    items = build()
    from collections import Counter
    h = write_jsonl(SETS / "t2_failure_class.jsonl", items)
    print(len(items), Counter(i["label"] for i in items), Counter((i["label"], i["det_baseline"]["label"]) for i in items), h)
