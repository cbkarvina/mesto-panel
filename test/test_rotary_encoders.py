#!/usr/bin/env python3
import argparse
import time

from mcp23017 import MCP23017, MCP23017Error
from panel_inputs import PanelInputs


LETTERS = "ABCDEFGHIJ"


def test_rotary_encoders(
    busnum: int = 1,
    address: int = 0x20,
    enc1_a: int = 11,
    enc1_b: int = 12,
    enc2_a: int = 13,
    enc2_b: int = 14,
    poll_interval_ms: int = 2,
    enc1_reverse: bool = False,
    enc2_reverse: bool = False,
    enc1_swap_ab: bool = False,
    enc2_swap_ab: bool = False,
    debug: bool = False,
):
    """Read two EC11 encoders and print rotation events and A-J positions."""
    mcp = MCP23017(address=address, busnum=busnum)
    inputs = PanelInputs(poll_interval_ms=poll_interval_ms)

    enc1_pin_a = enc1_b if enc1_swap_ab else enc1_a
    enc1_pin_b = enc1_a if enc1_swap_ab else enc1_b
    enc2_pin_a = enc2_b if enc2_swap_ab else enc2_a
    enc2_pin_b = enc2_a if enc2_swap_ab else enc2_b

    inputs.add_encoder(
        "lock_encoder_1",
        mcp,
        pin_a=enc1_pin_a,
        pin_b=enc1_pin_b,
        reverse=enc1_reverse,
    )
    inputs.add_encoder(
        "lock_encoder_2",
        mcp,
        pin_a=enc2_pin_a,
        pin_b=enc2_pin_b,
        reverse=enc2_reverse,
    )

    positions = {
        "lock_encoder_1": 0,
        "lock_encoder_2": 0,
    }

    def _label(name: str) -> str:
        return LETTERS[positions[name]]

    def _on_event(ev):
        if ev.name not in positions:
            return

        if ev.event_type == "rotated_cw":
            positions[ev.name] = (positions[ev.name] + 1) % len(LETTERS)
            direction = "CW"
        elif ev.event_type == "rotated_ccw":
            positions[ev.name] = (positions[ev.name] - 1) % len(LETTERS)
            direction = "CCW"
        else:
            return

        l1 = _label("lock_encoder_1")
        l2 = _label("lock_encoder_2")
        match = "MATCH" if l1 == l2 else "----"
        print(
            f"{ev.name:12s} {direction:3s} -> "
            f"lock_encoder_1={l1} lock_encoder_2={l2} {match}"
        )

    inputs.on_event(_on_event)

    print("Rotary encoder test started")
    print(f"MCP address=0x{address:02X}, bus={busnum}")
    print(
        f"enc1 pins A/B={enc1_a}/{enc1_b}, "
        f"enc2 pins A/B={enc2_a}/{enc2_b}, poll={poll_interval_ms} ms"
    )
    print(
        f"enc1 reverse={enc1_reverse} swap_ab={enc1_swap_ab}, "
        f"enc2 reverse={enc2_reverse} swap_ab={enc2_swap_ab}"
    )
    print("Rotate knobs. Press Ctrl+C to stop.")

    if debug:
        print("DEBUG ON: printing raw AB state changes")

    def _raw_state(pin_a: int, pin_b: int):
        a = mcp.digital_read(pin_a)
        b = mcp.digital_read(pin_b)
        return a, b, ((a & 0x1) << 1) | (b & 0x1)

    last_dbg_1 = _raw_state(enc1_pin_a, enc1_pin_b)
    last_dbg_2 = _raw_state(enc2_pin_a, enc2_pin_b)

    try:
        while True:
            inputs.update()

            if debug:
                dbg_1 = _raw_state(enc1_pin_a, enc1_pin_b)
                dbg_2 = _raw_state(enc2_pin_a, enc2_pin_b)

                if dbg_1 != last_dbg_1:
                    print(
                        "DBG enc1 "
                        f"A={dbg_1[0]} B={dbg_1[1]} state={dbg_1[2]:02b} "
                        f"(prev={last_dbg_1[2]:02b})"
                    )
                    last_dbg_1 = dbg_1

                if dbg_2 != last_dbg_2:
                    print(
                        "DBG enc2 "
                        f"A={dbg_2[0]} B={dbg_2[1]} state={dbg_2[2]:02b} "
                        f"(prev={last_dbg_2[2]:02b})"
                    )
                    last_dbg_2 = dbg_2

            time.sleep(inputs.poll_interval_s)
    except KeyboardInterrupt:
        print("\nStopping encoder test")
    finally:
        mcp.close()


def main():
    parser = argparse.ArgumentParser(description="Test two EC11 rotary encoders")
    parser.add_argument("--bus", type=int, default=1, help="I2C bus number (default: 1)")
    parser.add_argument(
        "--address",
        type=lambda x: int(x, 0),
        default=0x20,
        help="MCP23017 I2C address, e.g. 0x20 (default: 0x20)",
    )
    parser.add_argument("--enc1-a", type=int, default=11, help="Encoder 1 A pin")
    parser.add_argument("--enc1-b", type=int, default=12, help="Encoder 1 B pin")
    parser.add_argument("--enc2-a", type=int, default=13, help="Encoder 2 A pin")
    parser.add_argument("--enc2-b", type=int, default=14, help="Encoder 2 B pin")
    parser.add_argument(
        "--poll-ms",
        type=int,
        default=2,
        help="Poll interval in ms (default: 2)",
    )
    parser.add_argument(
        "--enc1-reverse",
        action="store_true",
        help="Reverse direction for encoder 1",
    )
    parser.add_argument(
        "--enc2-reverse",
        action="store_true",
        help="Reverse direction for encoder 2",
    )
    parser.add_argument(
        "--enc1-swap-ab",
        action="store_true",
        help="Swap A/B channels for encoder 1",
    )
    parser.add_argument(
        "--enc2-swap-ab",
        action="store_true",
        help="Swap A/B channels for encoder 2",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print raw A/B pin state changes",
    )
    args = parser.parse_args()

    try:
        test_rotary_encoders(
            busnum=args.bus,
            address=args.address,
            enc1_a=args.enc1_a,
            enc1_b=args.enc1_b,
            enc2_a=args.enc2_a,
            enc2_b=args.enc2_b,
            poll_interval_ms=args.poll_ms,
            enc1_reverse=args.enc1_reverse,
            enc2_reverse=args.enc2_reverse,
            enc1_swap_ab=args.enc1_swap_ab,
            enc2_swap_ab=args.enc2_swap_ab,
            debug=args.debug,
        )
    except MCP23017Error as exc:
        print(f"Failed to start rotary test: {exc}")


if __name__ == "__main__":
    main()
