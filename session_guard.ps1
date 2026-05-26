param(
    [ValidateSet("status", "cleanup", "recover", "health", "heal")]
    [string]$Action = "status",
    [int]$Port = 2036,
    [string]$HostName = "localhost",
    [string]$Version = "6.4",
    [string]$ComsolServer = "D:\COMSOL\bin\win64\comsolmphserver.exe",
    [string]$TempDir = "F:\simulation\comsol_tmp",
    [string]$JavaHeap = "16g",
    [int]$HealthTimeoutSec = 25,
    [double]$MaxConnectSec = 15.0,
    [string]$ProjectRoot = $PSScriptRoot
)

$ErrorActionPreference = "Stop"

function Get-PythonProcesses {
    Get-CimInstance Win32_Process |
        Where-Object { $_.Name -match "^(python|pythonw|py)(\.exe)?$" }
}

function Get-ControllersByCommandLine {
    param([string]$RootPath)
    $markers = @(
        "shared_session.py",
        "resident_control.py",
        "check_environment.py",
        "check_session_health.py",
        "Codex-into-Comsol-for-realtime-control-tutorial",
        $RootPath
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }

    Get-PythonProcesses | Where-Object {
        $cmd = $_.CommandLine
        if ([string]::IsNullOrWhiteSpace($cmd)) {
            return $false
        }
        foreach ($m in $markers) {
            if ($cmd.IndexOf($m, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
                return $true
            }
        }
        return $false
    }
}

function Get-ControllersByTcpPort {
    param([int]$TargetPort)
    $conns = @()
    try {
        $conns = @(Get-NetTCPConnection -State Established -RemotePort $TargetPort -ErrorAction Stop)
    } catch {
        $conns = @()
    }
    if (-not $conns) {
        return @()
    }

    $ownerIds = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    if (-not $ownerIds) {
        return @()
    }

    Get-PythonProcesses | Where-Object { $ownerIds -contains $_.ProcessId }
}

function Get-TargetControllers {
    param(
        [string]$RootPath,
        [int]$TargetPort
    )
    $byCmd = @(Get-ControllersByCommandLine -RootPath $RootPath)
    $byTcp = @(Get-ControllersByTcpPort -TargetPort $TargetPort)
    ($byCmd + $byTcp) | Sort-Object ProcessId -Unique
}

function Resolve-ProcessName {
    param([int]$ProcessId)
    try {
        return (Get-Process -Id $ProcessId -ErrorAction Stop).ProcessName
    } catch {
        return "<exited>"
    }
}

function Test-ServerListening {
    param([int]$TargetPort)
    try {
        return @(Get-NetTCPConnection -State Listen -LocalPort $TargetPort -ErrorAction Stop).Count -gt 0
    } catch {
        return $false
    }
}

function Get-PythonExecutable {
    param([string]$RootPath)
    $venvPython = Join-Path $RootPath ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }
    return "python"
}

function Invoke-ApiHealthCheck {
    param(
        [string]$RootPath,
        [string]$HostName,
        [int]$TargetPort,
        [string]$VersionTag,
        [int]$TimeoutSec,
        [double]$MaxConnectSeconds
    )

    $healthScript = Join-Path $RootPath "check_session_health.py"
    if (-not (Test-Path $healthScript)) {
        Write-Host ("[FAIL] Health script missing: {0}" -f $healthScript)
        return $false
    }

    $pythonExe = Get-PythonExecutable -RootPath $RootPath
    $args = "`"$healthScript`" --host $HostName --port $TargetPort --version $VersionTag --max-connect-seconds $MaxConnectSeconds"

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $pythonExe
    $psi.Arguments = $args
    $psi.WorkingDirectory = $RootPath
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi

    try {
        $null = $proc.Start()
    } catch {
        Write-Host ("[FAIL] Cannot start health process: {0}" -f $_.Exception.Message)
        return $false
    }

    if (-not $proc.WaitForExit($TimeoutSec * 1000)) {
        try {
            $proc.Kill()
            $null = $proc.WaitForExit(2000)
        } catch {
        }
        Write-Host ("[FAIL] API health check timeout after {0}s." -f $TimeoutSec)
        return $false
    }

    $stdout = $proc.StandardOutput.ReadToEnd().Trim()
    $stderr = $proc.StandardError.ReadToEnd().Trim()
    if (-not [string]::IsNullOrWhiteSpace($stdout)) {
        Write-Host $stdout
    }
    if (-not [string]::IsNullOrWhiteSpace($stderr)) {
        Write-Host ("[stderr] {0}" -f $stderr)
    }

    if ($proc.ExitCode -eq 0) {
        Write-Host "[OK] API health check passed."
        return $true
    }

    Write-Host ("[FAIL] API health check failed with exit code {0}." -f $proc.ExitCode)
    return $false
}

function Show-Status {
    param(
        [string]$RootPath,
        [int]$TargetPort
    )
    Write-Host "=== Session Status (port $TargetPort) ==="

    $listeners = @()
    try {
        $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $TargetPort -ErrorAction Stop)
    } catch {
        $listeners = @()
    }
    if ($listeners) {
        foreach ($l in $listeners) {
            $name = Resolve-ProcessName -ProcessId $l.OwningProcess
            Write-Host ("LISTEN  pid={0} name={1} local={2}:{3}" -f $l.OwningProcess, $name, $l.LocalAddress, $l.LocalPort)
        }
    } else {
        Write-Host "LISTEN  <none>"
    }

    $clients = @()
    try {
        $clients = @(Get-NetTCPConnection -State Established -RemotePort $TargetPort -ErrorAction Stop)
    } catch {
        $clients = @()
    }
    if ($clients) {
        foreach ($c in $clients) {
            $name = Resolve-ProcessName -ProcessId $c.OwningProcess
            Write-Host ("CLIENT  pid={0} name={1} local={2}:{3} -> remote={4}:{5}" -f $c.OwningProcess, $name, $c.LocalAddress, $c.LocalPort, $c.RemoteAddress, $c.RemotePort)
        }
    } else {
        Write-Host "CLIENT  <none>"
    }

    $targets = @(Get-TargetControllers -RootPath $RootPath -TargetPort $TargetPort)
    if ($targets) {
        Write-Host "PYCTRL  candidates:"
        foreach ($t in $targets) {
            Write-Host ("  pid={0} name={1}" -f $t.ProcessId, $t.Name)
        }
    } else {
        Write-Host "PYCTRL  <none>"
    }
}

function Cleanup-Controllers {
    param(
        [string]$RootPath,
        [int]$TargetPort
    )
    $targets = @(Get-TargetControllers -RootPath $RootPath -TargetPort $TargetPort)
    if (-not $targets) {
        Write-Host "[INFO] No stale Python controller processes found."
        return
    }

    foreach ($t in $targets) {
        try {
            Stop-Process -Id $t.ProcessId -Force -ErrorAction Stop
            Write-Host ("[INFO] Stopped stale controller pid={0} name={1}" -f $t.ProcessId, $t.Name)
        } catch {
            Write-Host ("[WARN] Failed to stop pid={0}: {1}" -f $t.ProcessId, $_.Exception.Message)
        }
    }
}

function Restart-ComsolServer {
    param(
        [string]$ServerPath,
        [int]$TargetPort,
        [string]$TmpDir,
        [string]$Heap
    )
    if (-not (Test-Path $ServerPath)) {
        throw "COMSOL server executable not found: $ServerPath"
    }
    if (-not (Test-Path $TmpDir)) {
        New-Item -ItemType Directory -Path $TmpDir | Out-Null
    }

    $servers = @(Get-Process -Name comsolmphserver -ErrorAction SilentlyContinue)
    foreach ($s in $servers) {
        try {
            Stop-Process -Id $s.Id -Force -ErrorAction Stop
            Write-Host ("[INFO] Stopped existing comsolmphserver pid={0}" -f $s.Id)
        } catch {
            Write-Host ("[WARN] Failed to stop comsolmphserver pid={0}: {1}" -f $s.Id, $_.Exception.Message)
        }
    }

    Start-Sleep -Seconds 2
    $oldTemp = $env:TEMP
    $oldTmp = $env:TMP
    $env:TEMP = $TmpDir
    $env:TMP = $TmpDir
    $arg = "-multi on -login auto -port $TargetPort -tmpdir `"$TmpDir`" -J-Xmx$Heap"
    $p = Start-Process -FilePath $ServerPath -ArgumentList $arg -WindowStyle Hidden -PassThru
    $env:TEMP = $oldTemp
    $env:TMP = $oldTmp
    Start-Sleep -Seconds 4
    Write-Host ("[INFO] Started comsolmphserver pid={0}" -f $p.Id)
    Write-Host ("[INFO] COMSOL temp dir: {0}" -f $TmpDir)
    Write-Host ("[INFO] Java heap: {0}" -f $Heap)
}

switch ($Action) {
    "status" {
        Show-Status -RootPath $ProjectRoot -TargetPort $Port
    }
    "cleanup" {
        Cleanup-Controllers -RootPath $ProjectRoot -TargetPort $Port
        Start-Sleep -Seconds 1
        Show-Status -RootPath $ProjectRoot -TargetPort $Port
    }
    "recover" {
        Cleanup-Controllers -RootPath $ProjectRoot -TargetPort $Port
        Restart-ComsolServer -ServerPath $ComsolServer -TargetPort $Port -TmpDir $TempDir -Heap $JavaHeap
        Start-Sleep -Seconds 1
        Show-Status -RootPath $ProjectRoot -TargetPort $Port
    }
    "health" {
        Show-Status -RootPath $ProjectRoot -TargetPort $Port
        if (-not (Test-ServerListening -TargetPort $Port)) {
            Write-Host "[FAIL] No COMSOL listener on target port."
            exit 2
        }
        $ok = Invoke-ApiHealthCheck -RootPath $ProjectRoot -HostName $HostName -TargetPort $Port -VersionTag $Version -TimeoutSec $HealthTimeoutSec -MaxConnectSeconds $MaxConnectSec
        if (-not $ok) {
            exit 3
        }
        exit 0
    }
    "heal" {
        Cleanup-Controllers -RootPath $ProjectRoot -TargetPort $Port

        if (-not (Test-ServerListening -TargetPort $Port)) {
            Write-Host "[WARN] Listener missing, restarting COMSOL server..."
            Restart-ComsolServer -ServerPath $ComsolServer -TargetPort $Port -TmpDir $TempDir -Heap $JavaHeap
            Start-Sleep -Seconds 1
        }

        $ok = Invoke-ApiHealthCheck -RootPath $ProjectRoot -HostName $HostName -TargetPort $Port -VersionTag $Version -TimeoutSec $HealthTimeoutSec -MaxConnectSeconds $MaxConnectSec
        if (-not $ok) {
            Write-Host "[WARN] Listener exists but API health failed, restarting COMSOL server..."
            Restart-ComsolServer -ServerPath $ComsolServer -TargetPort $Port -TmpDir $TempDir -Heap $JavaHeap
            Start-Sleep -Seconds 1
            $ok = Invoke-ApiHealthCheck -RootPath $ProjectRoot -HostName $HostName -TargetPort $Port -VersionTag $Version -TimeoutSec $HealthTimeoutSec -MaxConnectSeconds $MaxConnectSec
        }

        Show-Status -RootPath $ProjectRoot -TargetPort $Port
        if ($ok) {
            Write-Host "[INFO] Session healed and healthy."
            exit 0
        }
        Write-Host "[FAIL] Session still unhealthy after restart."
        exit 4
    }
}
