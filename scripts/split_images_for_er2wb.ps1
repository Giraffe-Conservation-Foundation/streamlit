<#
.SYNOPSIS
    Split a folder of survey JPEGs into small ZIPs sized for the ER2WB
    "Process my images" step, so each upload stays well under the size that
    hangs on a slow connection / the shared-process memory ceiling.

.DESCRIPTION
    ER2WB uploads run through Streamlit's file-uploader, which buffers the
    whole file in a memory-limited shared process. A single 400 MB ZIP can
    hang or crash. This script greedily bins your images into flat ZIPs of at
    most -MaxMB each; upload them one at a time in Step 3 and click
    "Rename my images" after each - batches accumulate, they don't replace.

.EXAMPLE
    .\split_images_for_er2wb.ps1 -Source "C:\surveys\NAM_EHGR\photos"

.EXAMPLE
    .\split_images_for_er2wb.ps1 -Source ".\photos" -MaxMB 30 -OutDir ".\batches"
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$Source,

    # Target max size per ZIP in MB. 40 keeps each upload comfortably under the
    # size that becomes unreliable on Streamlit Community Cloud.
    [double]$MaxMB = 40,

    # Where to write the batch ZIPs. Defaults to <Source>\_er2wb_batches.
    [string]$OutDir
)

if (-not (Test-Path -LiteralPath $Source)) {
    Write-Error "Source folder not found: $Source"
    exit 1
}
if (-not $OutDir) { $OutDir = Join-Path $Source "_er2wb_batches" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$maxBytes = [long]($MaxMB * 1MB)

$images = Get-ChildItem -LiteralPath $Source -File -Recurse -Include *.jpg, *.jpeg
if (-not $images) {
    Write-Error "No .jpg / .jpeg files found under $Source"
    exit 1
}

function Save-Batch {
    param([string[]]$Files, [int]$N)
    $name = Join-Path $OutDir ("batch_{0:D2}.zip" -f $N)
    if (Test-Path -LiteralPath $name) { Remove-Item -LiteralPath $name -Force }
    Compress-Archive -Path $Files -DestinationPath $name
    $mb = [math]::Round(((Get-Item -LiteralPath $name).Length / 1MB), 1)
    Write-Host ("  -> {0}  ({1} images, {2} MB)" -f (Split-Path $name -Leaf), $Files.Count, $mb) -ForegroundColor Green
}

$batch       = 1
$current     = @()
$currentSize = 0L
$total       = $images.Count
$done        = 0

foreach ($img in $images) {
    # Close the current batch before it would exceed the size cap
    if ($current.Count -gt 0 -and ($currentSize + $img.Length) -gt $maxBytes) {
        Save-Batch -Files $current -N $batch
        $batch++
        $current     = @()
        $currentSize = 0L
    }
    $current     += $img.FullName
    $currentSize += $img.Length
    $done++
    Write-Progress -Activity "Binning images into batches" `
        -Status "$done / $total" -PercentComplete (($done / $total) * 100)
}
if ($current.Count -gt 0) { Save-Batch -Files $current -N $batch }

Write-Progress -Activity "Binning images into batches" -Completed
Write-Host ""
Write-Host ("Done - {0} batch ZIP(s) written to:" -f $batch) -ForegroundColor Cyan
Write-Host "  $OutDir"
Write-Host ""
Write-Host "In ER2WB Step 3, upload each batch_NN.zip and click 'Rename my images'"
Write-Host "after each one. Batches accumulate; use 'Start Over' to clear everything."
