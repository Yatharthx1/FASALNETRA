param (
    [string]$Phone = ""
)

if ($Phone -ne "") {
    py -3.11 scripts/trigger_call.py $Phone
} else {
    py -3.11 scripts/trigger_call.py
}
