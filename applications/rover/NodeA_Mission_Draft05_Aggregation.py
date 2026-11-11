import asyncio
try:
    import aioconsole  # Required only for legacy terminal/file menus.
except ImportError:
    aioconsole = None  # GUI does not run the terminal menu.
import random
import os
import sys
import json
import time

from ud3tn_utils.aap2.aap2_client import AAP2AsyncUnixClient
from ud3tn_utils.aap2.generated import aap2_pb2


# ============================================================
# LOCAL MODIFIED AIOCOAP
# ============================================================

# Working-copy path: do not use old relative ../aiocoap/src from ud3tn.
# The modified Draft-04 fork on Rover is deliberately preferred to stock aiocoap.
from pathlib import Path
project_root = str(Path(__file__).resolve().parents[2] / 'vendor/aiocoap/src')
if not Path(project_root,'aiocoap').is_dir():
    raise RuntimeError('Missing local Draft-04 aiocoap fork: ' + project_root)
sys.path.insert(0, project_root)

import aiocoap
from aiocoap.message import Message
from aiocoap.numbers.codes import Code
from aiocoap.numbers.types import Type


# ============================================================
# ROVER / AAP2 SETTINGS
# ============================================================

SERVER_ADDRESS = '/tmp/ud3tn-ipn3-lab.aap2.sock'

COAP_DESTINATION = 'ipn:0.3.64'
FILE_DESTINATION = 'dtn://b.dtn/file'


# ============================================================
# COAP-OVER-BP SETTINGS
# ============================================================

# Draft-04 uses a 24-bit Message ID.
MAX_ID = 16777215

MID_STATE_FILE = str(Path.home() / 'coapbp/experiments/draft05-ipn/state/rover_aggregation_mid_state.json')

# Conservative reuse protection retained from the earlier client.
MID_REUSE_PROTECTION_SECONDS = 247

current_id = 1
recently_used_mids = {}

# Requests that have actually been transmitted
# and are waiting for responses.
#
# Key = Token
pending_requests = {}


# ============================================================
# AGGREGATION SETTINGS
# ============================================================

# Maximum number of CoAP messages placed in one Aggregate.
BUFFER_LIMIT = 2

# This is our experimental implementation value.
#
# Draft-04 defines MAX_AGGR_DELAY as the maximum time from
# generation of the first Single until the Aggregate is passed
# to BP. Draft-04 does not make "10 seconds" a universal default.
MAX_AGGR_DELAY_SECONDS = 10

# RFC 7252 / Draft-04 default NSTART is 1.
RFC7252_DEFAULT_NSTART = 1

# EXPERIMENTAL LAB VALUE.
#
# We use 5 so that this controlled test can actually demonstrate
# aggregation of several response-bearing requests.
#
# Do NOT describe 5 as the RFC default.
NSTART = 1  # Controlled aggregation experiment only

# Default NON_LIFETIME = MAX_LATENCY = 100 seconds.
#
# This is currently our lab-test value.
# For the long-delay DTN experiment it must later be reassessed
# using the measured DTN latency.
NON_LIFETIME_SECONDS = 100

# RFC 7252 default EXCHANGE_LIFETIME.
# Needed if CON support is tested later.
EXCHANGE_LIFETIME_SECONDS = 247


# ============================================================
# FILE SERVICE SETTINGS
# ============================================================

FILE_BUNDLE_LIFETIME_MS = 100000


# ============================================================
# AAP2 CLIENTS
#
# Rover has TWO application endpoints:
#
#   ipn:0.1.10
#   dtn://a.dtn/file
# ============================================================

coap_send_client = AAP2AsyncUnixClient(
    SERVER_ADDRESS
)

coap_receive_client = AAP2AsyncUnixClient(
    SERVER_ADDRESS
)

file_send_client = AAP2AsyncUnixClient(
    SERVER_ADDRESS
)

file_receive_client = AAP2AsyncUnixClient(
    SERVER_ADDRESS
)


def make_bundle_adu(destination, length, lifetime):
    """Use lifetime_ms if the installed AAP2 protobuf supports it.

    Some original µD3TN versions do not expose BundleADU.lifetime_ms;
    their node-level bundle lifetime default then applies instead. In that
    case the GUI must not claim requested lifetime was enforced.
    """
    fields = aap2_pb2.BundleADU.DESCRIPTOR.fields_by_name
    kwargs = {'dst_eid': destination, 'payload_length': length}
    if 'lifetime_ms' in fields:
        kwargs['lifetime_ms'] = lifetime
    else:
        print('WARNING: AAP2 BundleADU lacks lifetime_ms; '
              'requested lifetime NOT enforceable on this version')
        notify_gui('compat_warning', message='AAP2 lifetime_ms not supported')
    return aap2_pb2.BundleADU(**kwargs)


# Set by Mission Control after import. Each dynamically loaded module instance
# has a separate callback, buffer, MID state, pending table and AAP2 sockets.
EVENT_CALLBACK = None
EXPECTED_SERVER_SOURCE_EID = 'ipn:0.3.64'

def notify_gui(kind, **fields):
    if EVENT_CALLBACK is not None:
        try:
            EVENT_CALLBACK(kind, fields)
        except Exception as exc:
            print('GUI notification failed:', exc)


# ============================================================
# COAP AGGREGATION STATE
# ============================================================

# IMPORTANT:
#
# This contains Message objects, NOT encoded bytes.
#
# Encoding is delayed until flush time so we first know whether
# the BP payload is:
#
#   Single
#
# or
#
#   Aggregate
#
coap_buffer = []

coap_flusher_task = None

coap_flush_lock = asyncio.Lock()


# ============================================================
# MID PERSISTENCE
# ============================================================

def cleanup_expired_mids():

    now = time.time()

    expired_mids = [
        mid
        for mid, used_time
        in recently_used_mids.items()
        if (
            now - used_time
            >= MID_REUSE_PROTECTION_SECONDS
        )
    ]

    for mid in expired_mids:

        del recently_used_mids[mid]


def save_mid_state():

    state = {
        "next_mid": current_id,
        "recently_used_mids": recently_used_mids,
    }

    Path(MID_STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(
        MID_STATE_FILE,
        "w"
    ) as state_file:

        json.dump(
            state,
            state_file,
            indent=4
        )


def load_mid_state():

    global current_id
    global recently_used_mids


    if not os.path.exists(
        MID_STATE_FILE
    ):

        current_id = random.randint(
            1,
            MAX_ID
        )

        recently_used_mids = {}

        print(
            f"No previous MID state found. "
            f"Starting with random MID="
            f"{current_id}"
        )

        return


    try:

        with open(
            MID_STATE_FILE,
            "r"
        ) as state_file:

            state = json.load(
                state_file
            )


        current_id = int(
            state.get(
                "next_mid",
                random.randint(
                    1,
                    MAX_ID
                )
            )
        )


        recently_used_mids = {
            int(mid): float(used_time)
            for mid, used_time
            in state.get(
                "recently_used_mids",
                {}
            ).items()
        }


        cleanup_expired_mids()


        while (
            current_id
            in recently_used_mids
        ):

            current_id = (
                current_id
                % MAX_ID
            ) + 1


        print(
            f"Loaded MID state: "
            f"next MID={current_id}, "
            f"protected MIDs="
            f"{len(recently_used_mids)}"
        )


    except Exception as error:

        current_id = random.randint(
            1,
            MAX_ID
        )

        recently_used_mids = {}

        print(
            "Could not load MID state."
        )

        print(
            f"Reason: {error}"
        )

        print(
            f"Starting with random MID="
            f"{current_id}"
        )


def next_mid():

    global current_id


    cleanup_expired_mids()


    candidate_mid = (
        current_id
        % MAX_ID
    ) + 1


    while (
        candidate_mid
        in recently_used_mids
    ):

        candidate_mid = (
            candidate_mid
            % MAX_ID
        ) + 1


    current_id = candidate_mid
    save_mid_state()  # Reserve NEXT MID across crashes before BP transmission.


def record_used_mids(
    messages
):

    cleanup_expired_mids()

    used_time = time.time()


    for message in messages:

        recently_used_mids[
            message.mid
        ] = used_time


    save_mid_state()


# ============================================================
# TOKEN / PENDING REQUEST HANDLING
# ============================================================

def generate_unique_token():

    while True:

        candidate_token = os.urandom(
            4
        )


        buffered_tokens = {
            buffered_message.token
            for buffered_message
            in coap_buffer
            if buffered_message.token
        }


        if (
            candidate_token
            not in pending_requests
            and
            candidate_token
            not in buffered_tokens
        ):

            return candidate_token


def record_pending_requests(
    messages
):

    sent_time = time.time()


    for message in messages:

        pending_requests[
            message.token
        ] = {
            "mid": message.mid,
            "method": str(
                message.code
            ),
            "uri": (
                message.get_request_uri()
            ),
            "sent_time": sent_time,
        }


def remove_pending_requests(
    messages
):
    """
    Used only if BP submission fails.
    """

    for message in messages:

        pending_requests.pop(
            message.token,
            None
        )


# ============================================================
# .dtn.alt URI MAPPING
# ============================================================

def dtn_uri_host_to_node_eid(uri_host):
    """Map Draft-05 IPN URI authority to its node ID."""
    suffix = ".ipn.alt"
    if not uri_host or not uri_host.endswith(suffix):
        raise ValueError("Invalid IPN authority")

    parts = uri_host[:-len(suffix)].split(".")
    if len(parts) != 3 or not all(p.isdecimal() for p in parts):
        raise ValueError("Expected service.node.allocator.ipn.alt")

    service, node, allocator = map(int, parts)

    if any(x > 0xFFFFFFFF for x in (service, node, allocator)):
        raise ValueError("IPN component out of range")

    if (service, node, allocator) != (64, 3, 0):
        raise ValueError("Unexpected Earth CoAP authority")

    return "ipn:%d.%d.0" % (allocator, node)


# ============================================================
# NSTART
# ============================================================

def current_interaction_count():
    """
    Count requests that will become or already are
    outstanding to the Earth CoAP endpoint.

    Buffered messages are included because they will all become
    outstanding when the Aggregate is submitted.
    """

    return (
        len(pending_requests)
        +
        len(coap_buffer)
    )


def nstart_space_available():

    return (
        current_interaction_count()
        < NSTART
    )


# ============================================================
# BUNDLE LIFETIME
# ============================================================

def calculate_coap_bundle_lifetime_ms(
    messages
):

    number_of_messages = len(
        messages
    )


    has_con = any(
        message.mtype == Type.CON
        for message in messages
    )

    has_non = any(
        message.mtype == Type.NON
        for message in messages
    )


    # --------------------------------------------------------
    # SINGLE
    # --------------------------------------------------------

    if number_of_messages == 1:

        message = messages[0]


        if message.mtype == Type.CON:

            lifetime_seconds = (
                EXCHANGE_LIFETIME_SECONDS
            )


        elif message.mtype == Type.NON:

            lifetime_seconds = (
                NON_LIFETIME_SECONDS
            )


        else:

            raise ValueError(
                "A request must be CON or NON"
            )


    # --------------------------------------------------------
    # AGGREGATE
    # --------------------------------------------------------

    else:

        # All CON
        if (
            has_con
            and not has_non
        ):

            lifetime_seconds = (
                EXCHANGE_LIFETIME_SECONDS
                +
                MAX_AGGR_DELAY_SECONDS
            )


        # All NON
        elif (
            has_non
            and not has_con
        ):

            lifetime_seconds = (
                NON_LIFETIME_SECONDS
                -
                MAX_AGGR_DELAY_SECONDS
            )


        # Mixed CON + NON
        else:

            lifetime_seconds = (
                MAX_AGGR_DELAY_SECONDS
                +
                max(
                    EXCHANGE_LIFETIME_SECONDS,
                    NON_LIFETIME_SECONDS
                )
            )


    return (
        lifetime_seconds
        * 1000
    )


# ============================================================
# FLUSH CoAP BUFFER
#
# Draft-04:
#
#   1 message
#       -> Single
#       -> NO Payload-length
#
#   2+ messages
#       -> Aggregate
#       -> Payload-length in EVERY member
# ============================================================

async def flush_coap_buffer():

    global coap_flusher_task


    async with coap_flush_lock:


        if not coap_buffer:

            return


        # Work on the current batch.
        messages = list(
            coap_buffer
        )


        number_of_messages = len(
            messages
        )


        # ----------------------------------------------------
        # Verify every CoAP URI maps to the same Earth node.
        # ----------------------------------------------------

        expected_node_eid = (
            "ipn:0.3.0"
        )


        for message in messages:

            uri_host = (
                message.opt.uri_host
            )


            mapped_node_eid = (
                dtn_uri_host_to_node_eid(
                    uri_host
                )
            )


            if (
                mapped_node_eid
                != expected_node_eid
            ):

                raise ValueError(
                    "URI-to-DTN mapping mismatch: "
                    f"{uri_host} "
                    f"-> {mapped_node_eid}"
                )


        # ====================================================
        # SINGLE
        # ====================================================

        if number_of_messages == 1:

            message = messages[0]


            # Draft-04:
            #
            # Payload-length MUST NOT be present
            # in a Single message.
            #
            # We never assigned it while buffering.

            if (
                message.opt.payload_length
                is not None
            ):

                raise ValueError(
                    "Draft-04 violation: "
                    "Single message unexpectedly "
                    "contains Payload-length"
                )


            bundle_payload = (
                message.encode()
            )

            bundle_kind = (
                "Single"
            )


        # ====================================================
        # AGGREGATE
        # ====================================================

        else:

            encoded_messages = []


            for message in messages:

                # Draft-04:
                #
                # Payload-length is the number of
                # CoAP payload bytes in this member.

                message.opt.payload_length = (
                    len(
                        message.payload
                    )
                )


                encoded_message = (
                    message.encode()
                )


                encoded_messages.append(
                    encoded_message
                )


            # Aggregate = concatenated Single messages.
            bundle_payload = b''.join(
                encoded_messages
            )

            bundle_kind = (
                "Aggregate"
            )


        bundle_lifetime_ms = (
            calculate_coap_bundle_lifetime_ms(
                messages
            )
        )


        print()
        print("=" * 60)

        print(
            f"SENDING {bundle_kind.upper()} "
            f"COAP-OVER-BP BUNDLE"
        )

        print("=" * 60)

        print(
            f"Destination EID       : "
            f"{COAP_DESTINATION}"
        )

        print(
            f"Number of CoAP msgs   : "
            f"{number_of_messages}"
        )


        # ----------------------------------------------------
        # Show each member clearly
        # ----------------------------------------------------

        for index, message in enumerate(
            messages,
            start=1
        ):

            print()
            print(
                f"Member #{index}"
            )

            print(
                f"  Method         : "
                f"{message.code}"
            )

            print(
                f"  MID            : "
                f"{message.mid}"
            )

            print(
                f"  Token          : "
                f"{message.token.hex()}"
            )

            print(
                f"  URI            : "
                f"{message.get_request_uri()}"
            )


            if (
                bundle_kind
                == "Aggregate"
            ):

                print(
                    f"  Payload-length : "
                    f"{message.opt.payload_length}"
                )

            else:

                print(
                    "  Payload-length : "
                    "ABSENT"
                )


        print()
        print(
            f"BP payload size       : "
            f"{len(bundle_payload)} bytes"
        )

        print(
            f"Requested BP lifetime : "
            f"{bundle_lifetime_ms} ms"
        )


        # ----------------------------------------------------
        # Put Tokens in pending_requests BEFORE transmission.
        #
        # This avoids a race in which a very fast response
        # reaches the receiver before the Token is recorded.
        # ----------------------------------------------------

        record_pending_requests(
            messages
        )


        try:

            response = (
                await coap_send_client.send_adu_rpc(

                    make_bundle_adu(
                        COAP_DESTINATION,
                        len(bundle_payload),
                        bundle_lifetime_ms,
                    ),


                    bundle_payload,
                )
            )


        except Exception:

            # BP submission did not succeed.
            # These requests are therefore not outstanding.

            remove_pending_requests(
                messages
            )

            raise


        notify_gui('submitted', bundle_kind=bundle_kind, mids=[m.mid for m in messages],
                   tokens=[m.token.hex() for m in messages],
                   bytes=len(bundle_payload), lifetime_ms=bundle_lifetime_ms)
        # Successful BP submission (NOT a delivery acknowledgment):
        # protect the MIDs from reuse.
        record_used_mids(
            messages
        )


        if response.HasField(
            "bundle_headers"
        ):

            actual_lifetime_ms = (
                response
                .bundle_headers
                .lifetime_ms
            )


            print(
                f"uD3TN BP lifetime     : "
                f"{actual_lifetime_ms} ms"
            )


            if (
                actual_lifetime_ms
                == bundle_lifetime_ms
            ):

                print(
                    "Lifetime verification  : PASS"
                )

            else:

                print(
                    "Lifetime verification  : FAIL"
                )


        print()
        print(
            f"{bundle_kind} submission: PASS"
        )

        print("=" * 60)


        # Remove exactly the messages that were sent.
        del coap_buffer[
            :number_of_messages
        ]


        # ----------------------------------------------------
        # Stop aggregation timer if this was a manual/full flush.
        # ----------------------------------------------------

        current_task = (
            asyncio.current_task()
        )


        if (
            coap_flusher_task
            and
            coap_flusher_task
            is not current_task
        ):

            coap_flusher_task.cancel()


        coap_flusher_task = None


# ============================================================
# MAX_AGGR_DELAY TIMER
# ============================================================

async def start_coap_flusher():

    try:

        await asyncio.sleep(
            MAX_AGGR_DELAY_SECONDS
        )


        if coap_buffer:

            print()
            print(
                "MAX_AGGR_DELAY reached "
                f"({MAX_AGGR_DELAY_SECONDS} s)."
            )

            print(
                "Flushing CoAP buffer..."
            )


            await flush_coap_buffer()


    except asyncio.CancelledError:

        pass


# ============================================================
# QUEUE ONE COAP REQUEST
# ============================================================

async def queue_coap_request(command, resource_path=None, payload=None):
    """Queue a CoAP request. GUI supplies resource_path/payload directly."""

    global coap_flusher_task


    # --------------------------------------------------------
    # NSTART guard
    # --------------------------------------------------------

    if not nstart_space_available():

        print()
        print("=" * 60)
        print("NSTART LIMIT REACHED")
        print("=" * 60)

        print(
            f"Configured NSTART : "
            f"{NSTART}"
        )

        print(
            f"Pending requests  : "
            f"{len(pending_requests)}"
        )

        print(
            f"Buffered requests : "
            f"{len(coap_buffer)}"
        )

        print(
            "Wait for responses or flush "
            "the current buffer."
        )

        print("=" * 60)

        return


    # ========================================================
    # GET
    # ========================================================

    if command == "get":
        if resource_path is None:
            resource_path = await aioconsole.ainput('Enter resource name to GET: ')
        resource_path = str(resource_path).strip().lstrip('/')
        if not resource_path:
            raise ValueError('GET resource path cannot be empty')
        message = Message(
            code=Code.GET,
            uri='coap://64.3.0.ipn.alt/' + resource_path,
            mtype=Type.NON,
            mid=current_id,
            payload=b'get',  # Existing Draft-04 lab behavior; intentional.
        )


    # ========================================================
    # PUT
    # ========================================================

    elif command == "put":

        resource_name = (
            await aioconsole.ainput(
                "Enter resource name to PUT to: "
            )
        )


        value = (
            await aioconsole.ainput(
                "Enter value to PUT: "
            )
        )


        message = Message(
            code=Code.PUT,
            uri=(
                "coap://64.3.0.ipn.alt/"
                f"{resource_name}"
            ),
            mtype=Type.NON,
            mid=current_id,
            payload=value.encode(
                'utf-8'
            )
        )


    # ========================================================
    # POST
    # ========================================================

    elif command == "post":
        if resource_path is None:
            # Preserve original CLI behavior when not driven by GUI.
            resource_name = await aioconsole.ainput('Enter new resource name: ')
            resource_path = ''
            payload = resource_name.encode('utf-8')
        resource_path = str(resource_path).strip().lstrip('/')
        if payload is None:
            raise ValueError('POST payload is required')
        if isinstance(payload, str):
            payload = payload.encode('utf-8')
        message = Message(
            code=Code.POST,
            uri='coap://64.3.0.ipn.alt/' + resource_path,
            mtype=Type.NON,
            mid=current_id,
            payload=payload,
        )


    # ========================================================
    # DELETE
    # ========================================================

    elif command == "delete":

        resource_name = (
            await aioconsole.ainput(
                "Enter resource name to DELETE: "
            )
        )


        message = Message(
            code=Code.DELETE,
            uri=(
                "coap://64.3.0.ipn.alt/"
                f"{resource_name}"
            ),
            mtype=Type.NON,
            mid=current_id,
            payload=b"delete"
        )


    else:

        return


    # --------------------------------------------------------
    # Unique Token
    # --------------------------------------------------------

    message.token = (
        generate_unique_token()
    )


    # IMPORTANT:
    #
    # Do NOT set message.opt.payload_length here.
    #
    # We do not yet know whether this message will leave as:
    #
    #   Single
    #
    # or
    #
    #   Aggregate.
    # --------------------------------------------------------


    # Save MID in message, then advance state for next message.
    next_mid()


    notify_gui('queued', method=command.upper(), mid=message.mid,
               token=message.token.hex(), uri=message.get_request_uri())

    # Keep the Message object unencoded.
    coap_buffer.append(
        message
    )


    print()
    print("-" * 60)

    print(
        f"Queued {command.upper()}"
    )

    print(
        f"URI          : "
        f"{message.get_request_uri()}"
    )

    print(
        f"MID          : "
        f"{message.mid}"
    )

    print(
        f"Token        : "
        f"{message.token.hex()}"
    )

    print(
        "Payload-length: NOT SET YET"
    )

    print(
        f"Buffer       : "
        f"{len(coap_buffer)}"
        f"/{BUFFER_LIMIT}"
    )

    print(
        f"Interactions : "
        f"{current_interaction_count()}"
        f"/{NSTART}"
    )

    print("-" * 60)


    # --------------------------------------------------------
    # First message starts MAX_AGGR_DELAY timer.
    # --------------------------------------------------------

    if (
        coap_flusher_task is None
        or
        coap_flusher_task.done()
    ):

        coap_flusher_task = (
            asyncio.create_task(
                start_coap_flusher()
            )
        )


        print(
            f"Aggregation timer started: "
            f"{MAX_AGGR_DELAY_SECONDS} s"
        )


    # --------------------------------------------------------
    # Full buffer -> send immediately.
    # --------------------------------------------------------

    if (
        len(coap_buffer)
        >= BUFFER_LIMIT
    ):

        print(
            "Aggregation buffer full."
        )

        await flush_coap_buffer()


# ============================================================
# BACKGROUND COAP RESPONSE RECEIVER
# ============================================================

async def coap_receive_loop():

    while True:

        try:

            (
                adu_msg,
                response_payload
            ) = (
                await coap_receive_client.receive_adu()
            )


            await (
                coap_receive_client
                .send_response_status(
                    aap2_pb2.ResponseStatus
                    .RESPONSE_STATUS_SUCCESS
                )
            )


            response = Message.decode(
                response_payload
            )


            print()
            print()
            print("=" * 60)
            print("COAP RESPONSE RECEIVED")
            print("=" * 60)

            print(
                f"Source EID : "
                f"{adu_msg.src_eid}"
            )

            print(
                f"Code       : "
                f"{response.code}"
            )

            print(
                f"MID        : "
                f"{response.mid}"
            )

            print(
                f"Token      : "
                f"{response.token.hex()}"
            )


            # A response from an unexpected BP source must never satisfy
            # a Rover exchange even if its token happens to match.
            if adu_msg.src_eid != EXPECTED_SERVER_SOURCE_EID:
                notify_gui('rejected', reason='Unexpected response source',
                           src=adu_msg.src_eid, token=response.token.hex())
                continue

            original_request = pending_requests.get(response.token)
            if original_request is not None:
                pending_requests.pop(response.token, None)
            notify_gui('response', src=adu_msg.src_eid,
                       code=str(response.code), mid=response.mid,
                       token=response.token.hex(),
                       matched=original_request is not None,
                       method=(original_request or {}).get('method'),
                       uri=(original_request or {}).get('uri'),
                       payload=response.payload.decode('utf-8', errors='replace'))


            if (
                original_request
                is not None
            ):

                print(
                    "Token match: PASS"
                )

                print(
                    f"Request    : "
                    f"{original_request['method']} "
                    f"{original_request['uri']}"
                )

                print(
                    f"Request MID: "
                    f"{original_request['mid']}"
                )


            else:

                print(
                    "Token match: FAIL"
                )


            print(
                f"Payload    : "
                f"{response.payload.decode('utf-8', errors='ignore')}"
            )

            print(
                f"Type       : "
                f"{response.mtype}"
            )

            print(
                f"Pending    : "
                f"{len(pending_requests)}"
            )

            print("=" * 60)


        except asyncio.CancelledError:

            raise


        except Exception as error:

            print()
            print(
                "CoAP receive error:"
            )

            print(
                error
            )


# ============================================================
# COAP MENU
# ============================================================

async def coap_service():

    while True:

        print()
        print("=" * 60)
        print("ROVER — CoAP SERVICE")
        print("=" * 60)

        print(
            "Source endpoint      : "
            "ipn:0.1.10"
        )

        print(
            "Destination endpoint : "
            "ipn:0.3.64"
        )

        print(
            f"MAX_AGGR_DELAY       : "
            f"{MAX_AGGR_DELAY_SECONDS} s"
        )

        print(
            f"Aggregation buffer   : "
            f"{len(coap_buffer)}"
            f"/{BUFFER_LIMIT}"
        )

        print(
            f"Pending responses    : "
            f"{len(pending_requests)}"
        )

        print(
            f"NSTART               : "
            f"{NSTART} "
            f"(experimental; RFC default="
            f"{RFC7252_DEFAULT_NSTART})"
        )

        print()

        print(
            "Commands: "
            "post, put, get, delete, "
            "flush, status, back"
        )


        command = (
            await aioconsole.ainput(
                "Enter command: "
            )
        )


        command = (
            command
            .strip()
            .lower()
        )


        # ----------------------------------------------------
        # BACK
        # ----------------------------------------------------

        if command == "back":

            # Do not silently discard buffered CoAP messages.
            await flush_coap_buffer()

            return


        # ----------------------------------------------------
        # MANUAL FLUSH
        # ----------------------------------------------------

        elif command == "flush":

            if coap_buffer:

                await flush_coap_buffer()

            else:

                print(
                    "CoAP buffer is empty."
                )


        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        elif command == "status":

            print()
            print(
                f"Buffered messages : "
                f"{len(coap_buffer)}"
            )

            print(
                f"Pending responses : "
                f"{len(pending_requests)}"
            )

            print(
                f"NSTART            : "
                f"{NSTART}"
            )


        # ----------------------------------------------------
        # COAP METHODS
        # ----------------------------------------------------

        elif command in (
            "get",
            "put",
            "post",
            "delete"
        ):

            await queue_coap_request(
                command
            )


        else:

            print(
                "Unknown CoAP command."
            )


# ============================================================
# FILE BUNDLE SEND
# ============================================================

async def send_file_bundle(
    payload
):

    response = (
        await file_send_client.send_adu_rpc(

            aap2_pb2.BundleADU(
                dst_eid=(
                    FILE_DESTINATION
                ),
                payload_length=(
                    len(payload)
                ),
                lifetime_ms=(
                    FILE_BUNDLE_LIFETIME_MS
                ),
            ),

            payload,
        )
    )


    print(
        f"Bundle destination : "
        f"{FILE_DESTINATION}"
    )

    print(
        f"Requested lifetime : "
        f"{FILE_BUNDLE_LIFETIME_MS} ms"
    )


    if response.HasField(
        "bundle_headers"
    ):

        actual_lifetime = (
            response
            .bundle_headers
            .lifetime_ms
        )


        print(
            f"uD3TN lifetime     : "
            f"{actual_lifetime} ms"
        )


        if (
            actual_lifetime
            == FILE_BUNDLE_LIFETIME_MS
        ):

            print(
                "Lifetime verification: PASS"
            )

        else:

            print(
                "Lifetime verification: FAIL"
            )


# ============================================================
# FILE — LIST
# ============================================================

async def request_file_list():

    request_payload = (
        b"LIST_FILES"
    )


    print()
    print("FILE REQUEST")
    print("-" * 60)

    print(
        "Command     : LIST_FILES"
    )

    print(
        f"BP dst EID  : "
        f"{FILE_DESTINATION}"
    )

    print("-" * 60)


    await send_file_bundle(
        request_payload
    )


    print()
    print(
        "Waiting for Earth file list..."
    )


    (
        adu_msg,
        response_payload
    ) = (
        await file_receive_client.receive_adu()
    )


    await (
        file_receive_client
        .send_response_status(
            aap2_pb2.ResponseStatus
            .RESPONSE_STATUS_SUCCESS
        )
    )


    response_text = (
        response_payload.decode(
            'utf-8',
            errors='replace'
        )
    )


    if not response_text.startswith(
        "FILE_LIST\n"
    ):

        print(
            "Unexpected File-service response:"
        )

        print(
            response_text
        )

        return []


    lines = (
        response_text
        .splitlines()[1:]
    )


    files = []


    for line in lines:

        if "|" not in line:

            continue


        (
            filename,
            size_text
        ) = line.rsplit(
            "|",
            1
        )


        try:

            size = int(
                size_text
            )

        except ValueError:

            continue


        files.append(
            (
                filename,
                size
            )
        )


    return files


# ============================================================
# FILE — DOWNLOAD
# ============================================================

async def download_file(
    filename
):

    request_text = (
        f"GET_FILE:{filename}"
    )

    request_payload = (
        request_text.encode(
            'utf-8'
        )
    )


    print()
    print("FILE REQUEST")
    print("-" * 60)

    print(
        f"Command     : "
        f"{request_text}"
    )

    print(
        f"BP dst EID  : "
        f"{FILE_DESTINATION}"
    )

    print("-" * 60)


    await send_file_bundle(
        request_payload
    )


    print()
    print(
        f"Waiting for {filename}..."
    )


    (
        adu_msg,
        response_payload
    ) = (
        await file_receive_client.receive_adu()
    )


    await (
        file_receive_client
        .send_response_status(
            aap2_pb2.ResponseStatus
            .RESPONSE_STATUS_SUCCESS
        )
    )


    separator = (
        response_payload.find(
            b"\n"
        )
    )


    if separator == -1:

        print(
            "Invalid File-service response."
        )

        return


    header = (
        response_payload[
            :separator
        ].decode(
            'utf-8',
            errors='replace'
        )
    )


    file_data = (
        response_payload[
            separator + 1:
        ]
    )


    expected_header = (
        f"FILE_DATA:{filename}"
    )


    if header != expected_header:

        print(
            "Earth returned:"
        )

        print(
            response_payload.decode(
                'utf-8',
                errors='replace'
            )
        )

        return


    os.makedirs(
        "received_files",
        exist_ok=True
    )


    output_path = (
        os.path.join(
            "received_files",
            filename
        )
    )


    with open(
        output_path,
        'wb'
    ) as output_file:

        output_file.write(
            file_data
        )


    print()
    print("=" * 60)
    print("FILE RECEIVED SUCCESSFULLY")
    print("=" * 60)

    print(
        f"Source EID : "
        f"{adu_msg.src_eid}"
    )

    print(
        f"Filename   : "
        f"{filename}"
    )

    print(
        f"File size  : "
        f"{len(file_data)} bytes"
    )

    print(
        f"Saved to   : "
        f"{output_path}"
    )

    print("=" * 60)


# ============================================================
# FILE MENU
# ============================================================

async def file_service():

    while True:

        print()
        print("=" * 60)
        print("ROVER — FILE SERVICE")
        print("=" * 60)

        print(
            "Source endpoint      : "
            "dtn://a.dtn/file"
        )

        print(
            "Destination endpoint : "
            "dtn://b.dtn/file"
        )

        print()
        print(
            "Requesting available files "
            "from Earth..."
        )


        files = (
            await request_file_list()
        )


        if not files:

            print(
                "No files were returned by Earth."
            )

            return


        print()
        print("AVAILABLE EARTH FILES")
        print("-" * 60)


        for (
            index,
            (
                filename,
                size
            )
        ) in enumerate(
            files,
            start=1
        ):

            print(
                f"{index}. "
                f"{filename} "
                f"({size} bytes)"
            )


        print(
            f"{len(files) + 1}. Back"
        )

        print("-" * 60)


        choice = (
            await aioconsole.ainput(
                "Choose file number: "
            )
        )


        try:

            choice_number = int(
                choice
            )

        except ValueError:

            print(
                "Please enter a number."
            )

            continue


        if (
            choice_number
            == len(files) + 1
        ):

            return


        if not (
            1
            <= choice_number
            <= len(files)
        ):

            print(
                "Invalid file number."
            )

            continue


        filename = (
            files[
                choice_number - 1
            ][0]
        )


        print()
        print(
            f"Selected file: "
            f"{filename}"
        )


        await download_file(
            filename
        )


        again = (
            await aioconsole.ainput(
                "\nDownload another file? "
                "(yes/no): "
            )
        )


        if (
            again
            .strip()
            .lower()
            not in (
                "yes",
                "y"
            )
        ):

            return


# ============================================================
# MAIN SERVICE MENU
# ============================================================

async def service_menu():

    while True:

        print()
        print("=" * 60)
        print("ROVER MULTI-APPLICATION CLIENT")
        print("=" * 60)

        print(
            "DTN Node ID : "
            "dtn://a.dtn/"
        )

        print()
        print(
            "Choose service:"
        )

        print(
            "  1. CoAP"
        )

        print(
            "  2. File"
        )

        print(
            "  3. Exit"
        )

        print("=" * 60)


        choice = (
            await aioconsole.ainput(
                "Enter service: "
            )
        )


        choice = (
            choice
            .strip()
            .lower()
        )


        if choice in (
            "1",
            "coap"
        ):

            await coap_service()


        elif choice in (
            "2",
            "file"
        ):

            await file_service()


        elif choice in (
            "3",
            "exit"
        ):

            # Never silently lose queued CoAP messages.
            await flush_coap_buffer()

            print(
                "Rover client stopped."
            )

            return


        else:

            print(
                "Invalid service selection."
            )


# ============================================================
# MAIN
# ============================================================

async def main():
    raise RuntimeError('This module is a GUI-controlled Draft-04 engine. '
                       'Run Rover_Mission_Control_IPN.py instead.')

if __name__ == '__main__':
    asyncio.run(main())
