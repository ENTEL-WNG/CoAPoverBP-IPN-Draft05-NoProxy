-- Experimental CoAP-over-BPv7 Draft-05 payload dissector for IPN service 64.
-- For the modified aiocoap fork with a 24-bit CoAP Message ID.
-- Install on Earth only; this does not alter network traffic or project code.
-- Set PL_OPTION to the local fork's OptionNumber.PAYLOAD_LENGTH before use.
local PL_OPTION = 65000  -- Experimental Payload-length option in this aiocoap fork

local coapbp = Proto("coapbp05", "CoAP over BPv7 (experimental Draft-05/IPN)")
local f = {
  count = ProtoField.uint8("coapbp05.count", "CoAP message count", base.DEC),
  version = ProtoField.uint8("coapbp05.version", "Version", base.DEC),
  mtype = ProtoField.uint8("coapbp05.type", "Type", base.DEC,
                          {[0]="CON", [1]="NON", [2]="ACK", [3]="RST"}),
  code = ProtoField.uint8("coapbp05.code", "Code (encoded)", base.HEX),
  mid = ProtoField.uint24("coapbp05.mid", "24-bit Message ID", base.DEC),
  token = ProtoField.bytes("coapbp05.token", "Token"),
  option = ProtoField.uint32("coapbp05.option", "Option number", base.DEC),
  host = ProtoField.string("coapbp05.uri_host", "Uri-Host"),
  path = ProtoField.string("coapbp05.uri_path", "Uri-Path segment"),
  plen = ProtoField.uint32("coapbp05.payload_length", "Payload-length", base.DEC),
  payload = ProtoField.bytes("coapbp05.payload", "CoAP payload"),
  warning = ProtoField.string("coapbp05.warning", "Dissection warning")
}
coapbp.fields = f

local function read_extended(tvb, p, nibble, last)
  if nibble < 13 then return nibble, p end
  if nibble == 13 then
    if p >= last then return nil, p end
    return 13 + tvb(p,1):uint(), p + 1
  end
  if nibble == 14 then
    if p + 1 >= last then return nil, p end
    return 269 + tvb(p,2):uint(), p + 2
  end
  return nil, p  -- 15 is reserved
end

local function read_uint(tvb, p, n)
  local value = 0
  for i = p, p + n - 1 do
    value = value * 256 + tvb(i,1):uint()
  end
  return value
end

local function dissect_message(tvb, start, last, parent, index)
  if last - start < 5 then return nil, "Truncated 5-byte CoAP/BP header" end
  local first = tvb(start,1):uint()
  local version = math.floor(first / 64)
  local mtype = math.floor(first / 16) % 4
  local tkl = first % 16
  if version ~= 1 or tkl > 8 or start + 5 + tkl > last then
    return nil, "Invalid CoAP version, token length, or header"
  end

  local code = tvb(start + 1,1):uint()
  local code_text = string.format("%d.%02d", math.floor(code / 32), code % 32)
  local item = parent:add(coapbp, tvb(start,5),
                          "CoAP member #" .. index .. " — " .. code_text)
  item:add(f.version, tvb(start,1), version)
  item:add(f.mtype, tvb(start,1), mtype)
  item:add(f.code, tvb(start+1,1)):append_text(" (" .. code_text .. ")")
  item:add(f.mid, tvb(start+2,3))
  if tkl > 0 then item:add(f.token, tvb(start+5,tkl)) end

  local p = start + 5 + tkl
  local option_number = 0
  local payload_length = nil
  local saw_pl = false
  local end_of_message = nil
  local option_count = 0

  while p < last do
    if tvb(p,1):uint() == 255 then
      local payload_start = p + 1
      if payload_start >= last then return nil, "Payload marker has no payload" end
      local payload_size = payload_length or (last - payload_start)
      if payload_size > last - payload_start then
        return nil, "Payload-length extends past the BPv7 payload"
      end
      if payload_size > 0 then
        item:add(f.payload, tvb(payload_start, payload_size))
      end
      end_of_message = payload_start + payload_size
      break
    end

    option_count = option_count + 1
    if option_count > 128 then return nil, "Too many CoAP options" end
    local option_start = p
    local header = tvb(p,1):uint()
    p = p + 1
    local delta, newpos = read_extended(tvb, p, math.floor(header/16), last)
    if delta == nil then return nil, "Invalid/truncated option delta" end
    p = newpos
    local length
    length, newpos = read_extended(tvb, p, header % 16, last)
    if length == nil then return nil, "Invalid/truncated option length" end
    p = newpos
    if length > last - p then return nil, "Truncated CoAP option value" end
    option_number = option_number + delta
    local opt_item = item:add(f.option, tvb(option_start, 1), option_number)
    opt_item:append_text(" (" .. length .. " byte value)")
    if option_number == 3 then
      item:add(f.host, tvb(p,length), tvb(p,length):string())
    elseif option_number == 11 then
      item:add(f.path, tvb(p,length), tvb(p,length):string())
    elseif PL_OPTION > 0 and option_number == PL_OPTION then
      if length > 4 then return nil, "Payload-length exceeds supported uint32" end
      payload_length = read_uint(tvb, p, length)
      item:add(f.plen, tvb(p,length), payload_length)
      saw_pl = true
    end
    p = p + length
  end

  if end_of_message == nil then
    if saw_pl and payload_length == 0 then
      end_of_message = p
    elseif saw_pl and payload_length > 0 then
      return nil, "Payload-length provided but missing CoAP payload marker"
    else
      end_of_message = last  -- Single message without Payload-length
    end
  end
  if end_of_message <= start then return nil, "No forward progress" end
  item:set_len(end_of_message - start)
  return end_of_message, nil, saw_pl
end

function coapbp.dissector(tvb, pinfo, tree)
  local n = tvb:len()
  if n < 5 then return 0 end
  if math.floor(tvb(0,1):uint()/64) ~= 1 then return 0 end
  local root = tree:add(coapbp, tvb(), "CoAP over BPv7 (IPN service 64)")
  local offset, count, all_have_pl = 0, 0, true
  while offset < n and count < 32 do
    local finish, err, has_pl = dissect_message(tvb, offset, n, root, count+1)
    if not finish then
      root:add(f.warning, "Stopped at byte " .. offset .. ": " .. tostring(err))
      return n
    end
    count = count + 1
    all_have_pl = all_have_pl and has_pl
    offset = finish
  end
  if offset ~= n then
    root:add(f.warning, "Incomplete decoding: " .. (n-offset) .. " bytes remain")
  end
  root:add(f.count, count):set_generated(true)
  if count > 1 and not all_have_pl then
    root:add(f.warning, "Aggregate contains a member without Payload-length")
  end
  local kind = count > 1 and "Aggregate" or "Single"
  root:append_text(string.format(" — %s, %d CoAP message(s), %d bytes", kind, count, n))
  pinfo.cols.info:append(string.format(" | CoAP/BP %s (%d messages)", kind, count))
  return n
end

-- Wireshark BPv7 uses the destination ipn: service to choose its payload decoder.
-- Only experimental service 64 is affected. No TCP-port registration needed.
DissectorTable.get("bpv7.payload.ipn_serv"):add(64, coapbp)

-- Decode CoAP responses addressed to the Rover applications.
DissectorTable.get("bpv7.payload.ipn_serv"):add(10, coapbp)
DissectorTable.get("bpv7.payload.ipn_serv"):add(11, coapbp)
