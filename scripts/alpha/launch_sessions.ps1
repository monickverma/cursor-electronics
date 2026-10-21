<#
Alpha benchmark loop launcher.

Starts the benchmark-loop sessions (S1..S8) as headless Claude Code runs on
minimax-m3.1-flash:cloud through Ollama, each in its own git worktree, never
more at once than the Ollama plan allows. See
.claude/shared-memory/plan/benchmark_loop_plan.md.

  concurrency.txt  Ollama plan limit: Free 1, Pro 3, Max 10. Read every poll,
                   so it can be changed while the launcher runs. The master
                   session and every running session count against it.
  STOP             If present, nothing new starts; the launcher exits when
                   its sessions have finished.

Usage:  powershell -File scripts\alpha\launch_sessions.ps1 [-DryRun] [-MaxCycles 20] [-PollSeconds 60]
#>
param(
    [switch]$DryRun,
    [int]$DryRunSlots = 0,   # dry run only: pretend this many slots are free
    [int]$MaxCycles = 20,
    [int]$PollSeconds = 60
)

$ErrorActionPreference = 'Stop'
$Main     = 'C:\Users\KIIT\cursor-electronics'
$WtRoot   = 'C:\Users\KIIT\ce-wt'
$Shared   = 'C:\Users\KIIT\cursor-electronics-alpha'
$Prompts  = Join-Path $Main '.claude\shared-memory\alpha\sessions'
$Model    = 'minimax-m3.1-flash:cloud'
$Base     = 'alpha-program'

# Launch priority when slots are short (plan section 4).
$Sessions = @(
    @{ Id = 'S1'; Name = 'bench-corpus';  Branch = 'alpha/bench-corpus' },
    @{ Id = 'S2'; Name = 'bench-judge';   Branch = 'alpha/bench-judge' },
    @{ Id = 'S3'; Name = 'diagnose';      Branch = 'alpha/diagnose' },
    @{ Id = 'S7'; Name = 'gate';          Branch = 'alpha/integration' },
    @{ Id = 'S4'; Name = 'build-router';  Branch = 'alpha/build-router' },
    @{ Id = 'S5'; Name = 'build-physics'; Branch = 'alpha/build-physics' },
    @{ Id = 'S6'; Name = 'build-export';  Branch = 'alpha/build-export' },
    @{ Id = 'S8'; Name = 'competitors';   Branch = 'alpha/competitors' }
)

foreach ($d in @($WtRoot, $Shared, "$Shared\corpus", "$Shared\runs", "$Shared\logs")) {
    New-Item -ItemType Directory -Force $d | Out-Null
}
$ConcFile  = Join-Path $Shared 'concurrency.txt'
$StopFile  = Join-Path $Shared 'STOP'
$StateFile = Join-Path $Shared 'launcher_state.json'
if (-not (Test-Path $ConcFile)) { Set-Content $ConcFile '1' }

function Write-Log($msg) {
    $line = '{0}  {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Write-Host $line   # not Write-Output: that would leak into function return values
    Add-Content (Join-Path $Shared 'logs\launcher.log') $line
}

function Get-State {
    if (Test-Path $StateFile) {
        $raw = Get-Content $StateFile -Raw | ConvertFrom-Json
        $h = @{}
        foreach ($p in $raw.PSObject.Properties) { $h[$p.Name] = @{ Pid = $p.Value.Pid; Cycles = $p.Value.Cycles } }
        return $h
    }
    return @{}
}

function Save-State($state) { $state | ConvertTo-Json | Set-Content $StateFile }

function Get-MiniMaxCount {
    # Every Claude Code process on MiniMax: the master and any session we started.
    @(Get-CimInstance Win32_Process -Filter "Name='claude.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine -match [regex]::Escape($Model) }).Count
}

function Test-Alive($procId) {
    if (-not $procId) { return $false }
    return [bool](Get-Process -Id $procId -ErrorAction SilentlyContinue)
}

function Ensure-Worktree($s) {
    $path = Join-Path $WtRoot $s.Name
    if (Test-Path $path) { return $path }
    $exists = git -C $Main branch --list $s.Branch
    if ($exists) { git -C $Main worktree add $path $s.Branch | Out-Null }
    else         { git -C $Main worktree add -b $s.Branch $path $Base | Out-Null }
    $envFile = Join-Path $Main '.env'
    if (Test-Path $envFile) { Copy-Item $envFile (Join-Path $path '.env') }
    Write-Log "worktree $path on $($s.Branch)"
    return $path
}

function Start-SessionRun($s, $cycle) {
    $path   = Ensure-Worktree $s
    $prompt = Join-Path $Prompts "$($s.Id).md"
    $log    = Join-Path $Shared ("logs\{0}-{1:D3}.log" -f $s.Id, $cycle)
    $task   = "You are session $($s.Id) ($($s.Name)), cycle $cycle. Your full instructions are in the file $prompt . Read that file first and follow it exactly. Your worktree is $path ."
    $deny   = @(
        'Bash(git push --force:*)', 'Bash(git push -f:*)', 'Bash(git reset --hard:*)',
        'Bash(git checkout master:*)', 'Bash(git branch -D:*)', 'Bash(rm -rf /:*)'
    ) | ForEach-Object { '"' + $_ + '"' }
    $argLine = 'launch claude --model ' + $Model + ' -- -p "' + $task + '" --permission-mode bypassPermissions --max-turns 200 --disallowedTools ' + ($deny -join ' ')
    if ($DryRun) { Write-Log "DRYRUN $($s.Id): ollama $argLine  (cwd $path)"; return $null }
    $p = Start-Process -FilePath 'ollama' -ArgumentList $argLine -WorkingDirectory $path -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $log -RedirectStandardError ($log + '.err')
    Write-Log "started $($s.Id) cycle $cycle pid $($p.Id) log $log"
    return $p.Id
}

Write-Log "launcher up (dry run: $DryRun, max cycles $MaxCycles)"
$state = Get-State
while ($true) {
    $limit   = [int]((Get-Content $ConcFile -Raw).Trim())
    $running = Get-MiniMaxCount
    $mine    = @($Sessions | Where-Object { $state[$_.Id] -and (Test-Alive $state[$_.Id].Pid) })
    $free    = $limit - $running
    if ($DryRun -and $DryRunSlots -gt 0) { $free = $DryRunSlots }
    Write-Log "poll: limit $limit, MiniMax processes $running, free slots $free"

    if (Test-Path $StopFile) {
        if ($mine.Count -eq 0) { Write-Log 'STOP present and no session running: exiting'; break }
    } else {
        foreach ($s in $Sessions) {
            if ($free -le 0) { break }
            $st = $state[$s.Id]
            if ($st -and (Test-Alive $st.Pid)) { continue }
            $cycles = if ($st) { [int]$st.Cycles } else { 0 }
            if ($cycles -ge $MaxCycles) { continue }
            $procId = Start-SessionRun $s ($cycles + 1)
            if (-not $DryRun) {
                $state[$s.Id] = @{ Pid = $procId; Cycles = $cycles + 1 }
                Save-State $state
            }
            $free--
        }
    }
    if ($DryRun) { break }
    Start-Sleep -Seconds $PollSeconds
}
