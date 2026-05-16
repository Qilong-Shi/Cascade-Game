const BOARD_N = 8;
const RED = 0;
const BLUE = 1;
const EMPTY = -1;
const PLAY_LIMIT = 300;
const INITIAL_HEIGHT = 3;
const delayMs = 220;

const DIRS = [
  [-1, 0, "Up"],
  [1, 0, "Down"],
  [0, -1, "Left"],
  [0, 1, "Right"],
];

const LEVEL_BUDGETS = [0, 50, 150, 400, 800, 1600, 3200, 6400];
const RECORD_KEY = "cascade-arena-records";
const WORKER_URL = "/az/_app/immutable/workers/worker-JGcmZ3kC.js";

const els = {
  board: document.getElementById("board"),
  status: document.getElementById("status"),
  thinking: document.getElementById("thinking"),
  thinkingText: document.getElementById("thinkingText"),
  level: document.getElementById("level"),
  levelLabel: document.getElementById("levelLabel"),
  budgetLabel: document.getElementById("budgetLabel"),
  redPlayer: document.getElementById("redPlayer"),
  bluePlayer: document.getElementById("bluePlayer"),
  humanPanel: document.getElementById("humanPanel"),
  moveEatMode: document.getElementById("moveEatMode"),
  cascadeMode: document.getElementById("cascadeMode"),
  redName: document.getElementById("redName"),
  blueName: document.getElementById("blueName"),
  newGame: document.getElementById("newGame"),
  nextTurn: document.getElementById("nextTurn"),
  undoMove: document.getElementById("undoMove"),
  redoMove: document.getElementById("redoMove"),
  autoPlay: document.getElementById("autoPlay"),
  runTen: document.getElementById("runTen"),
  records: document.getElementById("records"),
  log: document.getElementById("log"),
  error: document.getElementById("error"),
  teacherEvalBar: document.getElementById("teacherEvalBar"),
  teacherRedEval: document.getElementById("teacherRedEval"),
  teacherBlueEval: document.getElementById("teacherBlueEval"),
  teacherDrawEval: document.getElementById("teacherDrawEval"),
};

const state = {
  game: null,
  players: {
    [RED]: "agent:agent",
    [BLUE]: "teacher",
  },
  playerOptions: [
    { id: "human", label: "Human" },
    { id: "teacher", label: "Teacher" },
    { id: "agent:agent", label: "agent" },
  ],
  humanActionMode: "move_eat",
  selectedHumanSource: null,
  history: [],
  redoStack: [],
  busy: false,
  autoMode: false,
  autoLoopActive: false,
  batchRemaining: 0,
  gameRecorded: false,
  gameNumber: 0,
  runId: 0,
  teacherWorker: null,
  teacherReady: false,
  pendingTeacherReady: null,
  pendingTeacherChoice: null,
};

class CascadeGame {
  constructor() {
    this.color = Array(64).fill(EMPTY);
    this.height = Array(64).fill(0);
    this.turnColor = RED;
    this.placementCount = 0;
    this.turnCount = 0;
    this.positionHistory = [];
    this.over = false;
    this.winner = null;
  }

  get phase() {
    return this.placementCount < 8 ? "placement" : "play";
  }

  idx(r, c) {
    return r * BOARD_N + c;
  }

  inside(r, c) {
    return r >= 0 && r < BOARD_N && c >= 0 && c < BOARD_N;
  }

  opponent(color) {
    return color === RED ? BLUE : RED;
  }

  adjacentToOpponent(r, c, color) {
    const opponent = this.opponent(color);
    return DIRS.some(([dr, dc]) => {
      const nr = r + dr;
      const nc = c + dc;
      return this.inside(nr, nc) && this.color[this.idx(nr, nc)] === opponent;
    });
  }

  legalActions() {
    if (this.over) return [];
    const out = [];
    const player = this.turnColor;

    if (this.phase === "placement") {
      for (let r = 0; r < BOARD_N; r += 1) {
        for (let c = 0; c < BOARD_N; c += 1) {
          const idx = this.idx(r, c);
          const besideOpponent = this.placementCount > 0 && this.adjacentToOpponent(r, c, player);
          if (this.color[idx] === EMPTY && !besideOpponent) out.push(r * BOARD_N + c);
        }
      }
      return out;
    }

    for (let r = 0; r < BOARD_N; r += 1) {
      for (let c = 0; c < BOARD_N; c += 1) {
        const idx = this.idx(r, c);
        if (this.color[idx] !== player) continue;

        const h = this.height[idx];
        const base = (r * BOARD_N + c) * 4;
        for (let di = 0; di < DIRS.length; di += 1) {
          const [dr, dc] = DIRS[di];
          const nr = r + dr;
          const nc = c + dc;
          if (!this.inside(nr, nc)) continue;

          const dest = this.idx(nr, nc);
          const destColor = this.color[dest];
          if (destColor === EMPTY || destColor === player) out.push(64 + base + di);
          else if (h >= this.height[dest]) out.push(320 + base + di);
        }

        if (h >= 2) {
          for (let di = 0; di < DIRS.length; di += 1) out.push(576 + base + di);
        }
      }
    }
    return out;
  }

  applyAction(action) {
    const legal = this.legalActions();
    if (!legal.includes(action)) {
      throw new Error(`Illegal action ${action}. Legal count: ${legal.length}`);
    }

    const decoded = decodeAction(action);
    const player = this.turnColor;

    if (decoded.type === "Place") {
      const idx = this.idx(decoded.r, decoded.c);
      this.color[idx] = player;
      this.height[idx] = INITIAL_HEIGHT;
      this.placementCount += 1;
    } else if (decoded.type === "Move") {
      const src = this.idx(decoded.r, decoded.c);
      const [dr, dc] = DIRS[decoded.di];
      const dest = this.idx(decoded.r + dr, decoded.c + dc);
      const moving = this.height[src];
      const destWasEmpty = this.color[dest] === EMPTY;
      this.color[dest] = player;
      this.height[dest] = destWasEmpty ? moving : this.height[dest] + moving;
      this.color[src] = EMPTY;
      this.height[src] = 0;
    } else if (decoded.type === "Eat") {
      const src = this.idx(decoded.r, decoded.c);
      const [dr, dc] = DIRS[decoded.di];
      const dest = this.idx(decoded.r + dr, decoded.c + dc);
      this.color[dest] = player;
      this.height[dest] = this.height[src];
      this.color[src] = EMPTY;
      this.height[src] = 0;
    } else {
      this.applyCascade(decoded.r, decoded.c, decoded.di, player);
    }

    this.turnCount += 1;
    this.turnColor = this.opponent(player);
    if (this.phase === "play") this.positionHistory.push(this.positionHash());
    this.updateGameOver();
  }

  applyCascade(r, c, di, player) {
    const [dr, dc] = DIRS[di];
    const src = this.idx(r, c);
    const count = this.height[src];
    this.color[src] = EMPTY;
    this.height[src] = 0;

    for (let step = 1; step <= count; step += 1) {
      const nr = r + dr * step;
      const nc = c + dc * step;
      if (!this.inside(nr, nc)) continue;

      const idx = this.idx(nr, nc);
      if (this.color[idx] !== EMPTY) this.pushStack(nr, nc, dr, dc);
      this.color[idx] = player;
      this.height[idx] = 1;
    }
  }

  pushStack(r, c, dr, dc) {
    const idx = this.idx(r, c);
    if (this.color[idx] === EMPTY) return;

    const nr = r + dr;
    const nc = c + dc;
    if (!this.inside(nr, nc)) {
      this.color[idx] = EMPTY;
      this.height[idx] = 0;
      return;
    }

    const dest = this.idx(nr, nc);
    if (this.color[dest] !== EMPTY) this.pushStack(nr, nc, dr, dc);
    this.color[dest] = this.color[idx];
    this.height[dest] = this.height[idx];
    this.color[idx] = EMPTY;
    this.height[idx] = 0;
  }

  positionHash() {
    return `${this.turnColor}|${this.color.join(",")}|${this.height.join(",")}`;
  }

  updateGameOver() {
    if (this.phase === "placement") return;

    const redTokens = this.tokenCount(RED);
    const blueTokens = this.tokenCount(BLUE);
    const playTurns = Math.max(0, this.turnCount - 8);
    const repetition = this.positionHistory.filter(x => x === this.positionHash()).length >= 3;
    const noMoves = this.legalActions().length === 0;

    if (redTokens === 0) {
      this.over = true;
      this.winner = BLUE;
    } else if (blueTokens === 0) {
      this.over = true;
      this.winner = RED;
    } else if (repetition || noMoves) {
      this.over = true;
      this.winner = null;
    } else if (playTurns >= PLAY_LIMIT) {
      this.over = true;
      this.winner = redTokens > blueTokens ? RED : blueTokens > redTokens ? BLUE : null;
    }
  }

  tokenCount(color) {
    return this.height.reduce((sum, h, idx) => sum + (this.color[idx] === color ? h : 0), 0);
  }

  stackCount(color) {
    return this.color.filter(x => x === color).length;
  }

  teacherSnapshot() {
    return {
      cells: this.color.map((color, idx) => [color, this.height[idx]]),
      turnColor: this.turnColor,
      placementCount: this.placementCount,
      turnCount: this.turnCount,
    };
  }
}

function decodeAction(action) {
  if (action < 64) return { type: "Place", r: Math.floor(action / 8), c: action % 8, di: 0 };
  if (action < 320) {
    const off = action - 64;
    const square = Math.floor(off / 4);
    return { type: "Move", r: Math.floor(square / 8), c: square % 8, di: off % 4 };
  }
  if (action < 576) {
    const off = action - 320;
    const square = Math.floor(off / 4);
    return { type: "Eat", r: Math.floor(square / 8), c: square % 8, di: off % 4 };
  }
  const off = action - 576;
  const square = Math.floor(off / 4);
  return { type: "Cascade", r: Math.floor(square / 8), c: square % 8, di: off % 4 };
}

function actionFromSource(source, kind, di) {
  const base = (source.r * 8 + source.c) * 4 + di;
  if (kind === "Move") return 64 + base;
  if (kind === "Eat") return 320 + base;
  return 576 + base;
}

function describeAction(action) {
  const a = decodeAction(action);
  if (a.type === "Place") return `PLACE(${a.r}-${a.c})`;
  return `${a.type.toUpperCase()}(${a.r}-${a.c}, ${DIRS[a.di][2]})`;
}

function coordKey(r, c) {
  return `${r},${c}`;
}

function colorName(color) {
  return color === RED ? "Red" : "Blue";
}

function colorId(color) {
  return color === RED ? "red" : "blue";
}

function playerKind(spec) {
  return spec.startsWith("agent:") ? "agent" : spec;
}

function playerLabel(spec) {
  const option = state.playerOptions.find(item => item.id === spec);
  return option ? option.label : spec;
}

function hasPythonAgent() {
  return Object.values(state.players).some(spec => playerKind(spec) === "agent");
}

function hasHumanPlayer() {
  return Object.values(state.players).some(spec => playerKind(spec) === "human");
}

function isHumanTurn() {
  const game = state.game;
  return game && !game.over && playerKind(state.players[game.turnColor]) === "human";
}

function isAiTurn() {
  const game = state.game;
  return game && !game.over && !isHumanTurn();
}

function currentPlayersPayload() {
  return {
    red: state.players[RED],
    blue: state.players[BLUE],
  };
}

async function api(path, payload = {}) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || `Request failed: ${path}`);
  return data;
}

function restartTeacher() {
  state.teacherWorker?.terminate();
  state.teacherReady = false;
  state.pendingTeacherChoice = null;

  return new Promise((resolve, reject) => {
    state.pendingTeacherReady = { resolve, reject };
    state.teacherWorker = new Worker(WORKER_URL, { type: "module" });
    state.teacherWorker.onmessage = handleTeacherMessage;
    state.teacherWorker.onerror = event => {
      const message = event.message || "Teacher worker failed";
      rejectTeacherReady(message);
      rejectTeacherChoice(message);
      showError(message);
    };
    state.teacherWorker.postMessage({
      type: "init",
      baseUrl: "/az",
      simBudget: currentTeacherBudget(),
    });
  });
}

function handleTeacherMessage(event) {
  const message = event.data;
  if (message.type === "ready") {
    state.teacherReady = true;
    const pending = state.pendingTeacherReady;
    state.pendingTeacherReady = null;
    if (pending) pending.resolve();
    updateControls();
    return;
  }

  if (message.type === "choice") {
    const pending = state.pendingTeacherChoice;
    state.pendingTeacherChoice = null;
    if (!pending) return;
    if (message.gameOver) pending.reject(new Error("Teacher reports the game is over."));
    else pending.resolve(message);
    return;
  }

  if (message.type === "progress") {
    if (state.busy && message.sims) {
      setThinking(true, `Teacher thinking... ${message.sims}/${currentTeacherBudget()} sims`);
    }
    return;
  }

  if (message.type === "eval") {
    updateEval(message.red, message.draw, message.blue);
    return;
  }

  if (message.type === "error") {
    const text = `Teacher worker: ${message.message}`;
    rejectTeacherReady(text);
    rejectTeacherChoice(text);
    showError(text);
  }
}

function rejectTeacherReady(message) {
  const pending = state.pendingTeacherReady;
  state.pendingTeacherReady = null;
  if (pending) pending.reject(new Error(message));
}

function rejectTeacherChoice(message) {
  const pending = state.pendingTeacherChoice;
  state.pendingTeacherChoice = null;
  if (pending) pending.reject(new Error(message));
}

function chooseTeacherAction() {
  if (!state.teacherReady || !state.teacherWorker) {
    return Promise.reject(new Error("Teacher model is not ready."));
  }
  return new Promise((resolve, reject) => {
    state.pendingTeacherChoice = { resolve, reject };
    state.teacherWorker.postMessage({ type: "choose", snapshot: state.game.teacherSnapshot() });
  });
}

function notifyTeacher(action) {
  if (state.teacherWorker) state.teacherWorker.postMessage({ type: "notify", action });
}

function requestTeacherEval() {
  if (state.teacherWorker) state.teacherWorker.postMessage({ type: "eval" });
}

async function notifyPython(color, action) {
  if (!hasPythonAgent()) return;
  await api("/api/notify", { color: colorId(color), action });
}

async function getPythonAction(color) {
  const data = await api("/api/agent_action", { color: colorId(color) });
  return data;
}

async function resetEngines(history, myRun) {
  await Promise.all([
    restartTeacher(),
    api("/api/new", { players: currentPlayersPayload() }),
  ]);
  if (myRun !== state.runId) return false;

  for (const move of history) {
    await notifyPython(move.color, move.action);
    notifyTeacher(move.action);
    if (myRun !== state.runId) return false;
  }

  requestTeacherEval();
  return true;
}

async function startGame({ keepAuto = false, batch = false } = {}) {
  const myRun = ++state.runId;
  clearError();
  state.busy = true;
  state.gameRecorded = false;
  state.gameNumber += 1;
  state.game = new CascadeGame();
  state.history = [];
  state.redoStack = [];
  state.selectedHumanSource = null;
  if (!keepAuto) {
    state.autoMode = false;
    state.batchRemaining = 0;
  }
  setThinking(true, "Starting game...");
  render();
  updateControls();

  try {
    const ok = await resetEngines([], myRun);
    if (!ok) return;
    logLine(`Game ${state.gameNumber} started. Red=${playerLabel(state.players[RED])}, Blue=${playerLabel(state.players[BLUE])}.`);
    render();
  } catch (error) {
    state.autoMode = false;
    state.batchRemaining = 0;
    showError(error.message);
  } finally {
    if (myRun === state.runId) {
      state.busy = false;
      setThinking(false);
      updateControls();
    }
  }

  if ((state.autoMode || batch) && myRun === state.runId) continueAuto(myRun);
}

async function rebuildFromHistory(nextHistory, nextRedoStack, message) {
  const myRun = ++state.runId;
  clearError();
  state.busy = true;
  state.autoMode = false;
  state.batchRemaining = 0;
  state.gameRecorded = false;
  state.selectedHumanSource = null;
  setThinking(true, "Rebuilding position...");
  updateControls();

  const nextGame = new CascadeGame();
  try {
    for (const move of nextHistory) nextGame.applyAction(move.action);
    state.game = nextGame;
    const ok = await resetEngines(nextHistory, myRun);
    if (!ok) return;
    state.history = nextHistory.slice();
    state.redoStack = nextRedoStack.slice();
    if (message) logLine(message);
    render();
  } catch (error) {
    showError(error.message);
  } finally {
    if (myRun === state.runId) {
      state.busy = false;
      setThinking(false);
      updateControls();
    }
  }
}

async function switchPlayersAndContinue(previousPlayers) {
  if (!state.game) {
    await startGame();
    return;
  }

  const myRun = ++state.runId;
  clearError();
  state.busy = true;
  state.autoMode = false;
  state.batchRemaining = 0;
  state.selectedHumanSource = null;
  setThinking(true, "Switching players...");
  render();
  updateControls();

  try {
    const ok = await resetEngines(state.history, myRun);
    if (!ok) return;
    logLine(`Players changed. Red=${playerLabel(state.players[RED])}, Blue=${playerLabel(state.players[BLUE])}.`);
    render();
  } catch (error) {
    state.players[RED] = previousPlayers[RED];
    state.players[BLUE] = previousPlayers[BLUE];
    try {
      await resetEngines(state.history, myRun);
    } catch {
      // Keep the visible position intact; the original error is more useful here.
    }
    showError(error.message);
    logLine(`Player switch failed: ${error.message}`);
    render();
  } finally {
    if (myRun === state.runId) {
      state.busy = false;
      setThinking(false);
      updateControls();
      render();
    }
  }
}

async function playOneTurn(myRun = state.runId) {
  const game = state.game;
  if (!game || game.over || state.busy || myRun !== state.runId) return;
  if (isHumanTurn()) {
    render();
    return;
  }

  state.busy = true;
  clearError();
  updateControls();

  const color = game.turnColor;
  const spec = state.players[color];
  const kind = playerKind(spec);
  const label = playerLabel(spec);
  const started = Date.now();
  let timer = null;

  try {
    setThinking(true, `${colorName(color)} ${label} thinking...`);
    timer = window.setInterval(() => {
      const elapsed = Math.floor((Date.now() - started) / 1000);
      setThinking(true, `${colorName(color)} ${label} thinking... ${elapsed}s`);
    }, 1000);

    await sleep(delayMs);
    const result = kind === "teacher" ? await chooseTeacherAction() : await getPythonAction(color);
    if (myRun !== state.runId) return;

    const action = Number(result.action);
    await applyMove(color, action, label);
    if (result.ms) logLine(`${label} responded in ${(result.ms / 1000).toFixed(2)}s.`);
  } catch (error) {
    state.autoMode = false;
    state.batchRemaining = 0;
    showError(error.message);
    logLine(`Stopped: ${error.message}`);
  } finally {
    if (timer !== null) window.clearInterval(timer);
    if (myRun === state.runId) {
      state.busy = false;
      setThinking(false);
      updateControls();
      render();
    }
  }
}

async function applyMove(color, action, label) {
  if (!state.game.legalActions().includes(action)) {
    throw new Error(`${colorName(color)} ${label} returned illegal action ${action} (${describeAction(action)}).`);
  }

  await notifyPython(color, action);
  state.game.applyAction(action);
  state.selectedHumanSource = null;
  notifyTeacher(action);

  state.history.push({ color, action, label });
  state.redoStack = [];
  logLine(`${colorName(color)} ${label}: ${describeAction(action)}`);
  render();

  if (state.game.over) finishGame();
}

async function continueAuto(myRun = state.runId) {
  if (state.autoLoopActive) return;
  state.autoLoopActive = true;

  try {
    while (state.autoMode && state.game && !state.game.over && !isHumanTurn() && myRun === state.runId) {
      await playOneTurn(myRun);
      if (!state.autoMode || !state.game || state.game.over || isHumanTurn() || myRun !== state.runId) break;
      await sleep(delayMs);
    }

    if (state.game?.over && state.batchRemaining > 1 && myRun === state.runId) {
      state.batchRemaining -= 1;
      await sleep(350);
      await startGame({ keepAuto: true, batch: true });
    } else if (state.game?.over) {
      state.batchRemaining = 0;
      updateControls();
    }
  } finally {
    state.autoLoopActive = false;
  }
}

async function undoMove() {
  if (state.busy || state.history.length === 0) return;
  const undone = state.history[state.history.length - 1];
  const nextHistory = state.history.slice(0, -1);
  const nextRedo = [undone, ...state.redoStack];
  await rebuildFromHistory(nextHistory, nextRedo, `Undo: ${colorName(undone.color)} ${undone.label} ${describeAction(undone.action)}`);
}

async function redoMove() {
  if (state.busy || state.redoStack.length === 0) return;
  const move = state.redoStack[0];
  const nextHistory = [...state.history, move];
  const nextRedo = state.redoStack.slice(1);
  await rebuildFromHistory(nextHistory, nextRedo, `Redo: ${colorName(move.color)} ${move.label} ${describeAction(move.action)}`);
}

function finishGame() {
  if (!state.game || state.gameRecorded) return;
  state.gameRecorded = true;

  const result = state.game.winner === null ? "Draw" : `${colorName(state.game.winner)} wins`;
  saveRecord({
    result,
    redPlayer: playerLabel(state.players[RED]),
    bluePlayer: playerLabel(state.players[BLUE]),
    red: state.game.tokenCount(RED),
    blue: state.game.tokenCount(BLUE),
    turns: state.game.turnCount,
  });
  renderRecords();
  logLine(`Game over: ${result}.`);
}

function humanHighlights() {
  const out = new Set();
  const game = state.game;
  if (!isHumanTurn()) return out;

  if (game.phase === "placement") {
    for (const action of game.legalActions()) {
      const a = decodeAction(action);
      out.add(coordKey(a.r, a.c));
    }
    return out;
  }

  const source = state.selectedHumanSource;
  if (!source) return out;
  for (const action of game.legalActions()) {
    const a = decodeAction(action);
    if (a.r !== source.r || a.c !== source.c) continue;
    if (state.humanActionMode === "cascade" && a.type !== "Cascade") continue;
    if (state.humanActionMode !== "cascade" && a.type === "Cascade") continue;
    const [dr, dc] = DIRS[a.di];
    const nr = source.r + dr;
    const nc = source.c + dc;
    if (game.inside(nr, nc)) out.add(coordKey(nr, nc));
  }
  return out;
}

function humanActionForClick(r, c) {
  const game = state.game;
  if (!isHumanTurn()) return null;

  if (game.phase === "placement") {
    const action = r * BOARD_N + c;
    return game.legalActions().includes(action) ? action : null;
  }

  const source = state.selectedHumanSource;
  if (!source) return null;

  for (const action of game.legalActions()) {
    const a = decodeAction(action);
    if (a.r !== source.r || a.c !== source.c) continue;
    if (state.humanActionMode === "cascade" && a.type !== "Cascade") continue;
    if (state.humanActionMode !== "cascade" && a.type === "Cascade") continue;
    const [dr, dc] = DIRS[a.di];
    if (source.r + dr === r && source.c + dc === c) return action;
  }
  return null;
}

async function handleHumanCellClick(r, c) {
  if (!isHumanTurn() || state.busy) return;
  clearError();

  const action = humanActionForClick(r, c);
  if (action !== null) {
    state.busy = true;
    updateControls();
    try {
      const color = state.game.turnColor;
      await applyMove(color, action, "Human");
    } catch (error) {
      showError(error.message);
    } finally {
      state.busy = false;
      setThinking(false);
      updateControls();
      render();
    }
    if (state.autoMode && state.game && !state.game.over && !isHumanTurn()) continueAuto(state.runId);
    return;
  }

  if (state.game.phase === "play") {
    const idx = r * BOARD_N + c;
    if (state.game.color[idx] === state.game.turnColor) {
      state.selectedHumanSource = { r, c };
      render();
      return;
    }
    state.selectedHumanSource = null;
  }
  render();
}

async function handleCascadeDirection(di) {
  const game = state.game;
  const source = state.selectedHumanSource;
  if (!isHumanTurn() || state.busy || !source || state.humanActionMode !== "cascade") return;

  const action = actionFromSource(source, "Cascade", di);
  if (!game.legalActions().includes(action)) return;

  state.busy = true;
  updateControls();
  try {
    const color = game.turnColor;
    await applyMove(color, action, "Human");
  } catch (error) {
    showError(error.message);
  } finally {
    state.busy = false;
    updateControls();
    render();
  }
  if (state.autoMode && state.game && !state.game.over && !isHumanTurn()) continueAuto(state.runId);
}

function render() {
  renderBoard();
  renderStatus();
  updatePlayerLabels();
  updateCascadeButtons();
  updateControls();
}

function renderBoard() {
  els.board.innerHTML = "";
  const game = state.game;
  const highlights = humanHighlights();

  for (let r = 0; r < BOARD_N; r += 1) {
    for (let c = 0; c < BOARD_N; c += 1) {
      const idx = r * BOARD_N + c;
      const cell = document.createElement("div");
      cell.className = "cell";
      if (isHumanTurn()) cell.classList.add("clickable");
      if (state.selectedHumanSource?.r === r && state.selectedHumanSource?.c === c) {
        cell.classList.add("selected");
      }
      if (highlights.has(coordKey(r, c))) cell.classList.add("highlight");
      cell.addEventListener("click", () => handleHumanCellClick(r, c));

      if (game && game.color[idx] !== EMPTY) {
        const stack = document.createElement("div");
        stack.className = `stack ${game.color[idx] === RED ? "red" : "blue"}`;
        stack.textContent = game.height[idx];
        cell.appendChild(stack);
      }
      els.board.appendChild(cell);
    }
  }
}

function renderStatus() {
  const game = state.game;
  if (!game) {
    els.status.textContent = state.teacherReady ? "Ready" : "Loading teacher model...";
    return;
  }

  const phase = game.phase === "placement"
    ? `placement ${Math.min(game.placementCount + 1, 8)}/8`
    : `turn ${Math.max(1, game.turnCount - 7)}/${PLAY_LIMIT}`;

  if (game.over) {
    els.status.textContent = game.winner === null ? "Game over - draw" : `Game over - ${colorName(game.winner)} wins`;
    return;
  }

  const colorClass = game.turnColor === RED ? "red" : "blue";
  const actor = playerLabel(state.players[game.turnColor]);
  const suffix = isHumanTurn() ? "human to play" : `${actor} to play`;
  els.status.innerHTML = `<strong class="${colorClass}">${colorName(game.turnColor)}</strong> ${suffix} - ${phase}`;
}

function updateEval(red, draw, blue) {
  const total = Math.max(0.0001, red + draw + blue);
  const rp = red / total;
  const dp = draw / total;
  const bp = blue / total;
  els.teacherEvalBar.style.setProperty("--red", `${rp * 100}%`);
  els.teacherEvalBar.style.setProperty("--draw", `${dp * 100}%`);
  els.teacherEvalBar.style.setProperty("--blue", `${bp * 100}%`);
  els.teacherRedEval.textContent = percent(rp);
  els.teacherDrawEval.textContent = percent(dp);
  els.teacherBlueEval.textContent = percent(bp);
}

function percent(value) {
  return `${Math.round(value * 100)}%`;
}

function setThinking(show, text = "") {
  els.thinking.classList.toggle("show", show);
  els.thinkingText.textContent = text;
}

function showError(text) {
  els.error.textContent = text;
  els.error.classList.add("show");
}

function clearError() {
  els.error.textContent = "";
  els.error.classList.remove("show");
}

function logLine(text) {
  const at = new Date().toLocaleTimeString();
  els.log.textContent = `[${at}] ${text}\n${els.log.textContent}`;
}

function saveRecord(record) {
  const records = getRecords();
  records.unshift({ ...record, at: new Date().toLocaleTimeString() });
  localStorage.setItem(RECORD_KEY, JSON.stringify(records.slice(0, 10)));
}

function getRecords() {
  try {
    return JSON.parse(localStorage.getItem(RECORD_KEY) || "[]");
  } catch {
    return [];
  }
}

function renderRecords() {
  const records = getRecords();
  els.records.innerHTML = "";
  if (records.length === 0) {
    const item = document.createElement("li");
    item.className = "record";
    item.textContent = "No games yet.";
    els.records.appendChild(item);
    return;
  }

  for (const record of records.slice(0, 10)) {
    const item = document.createElement("li");
    item.className = "record";
    const matchup = record.redPlayer && record.bluePlayer
      ? `${record.redPlayer} vs ${record.bluePlayer}`
      : "Unknown players";
    item.innerHTML = `<strong>${record.result}</strong><span>${matchup}, ${record.turns} turns, R${record.red}-B${record.blue}</span>`;
    els.records.appendChild(item);
  }
}

function renderPlayerOptions() {
  for (const select of [els.redPlayer, els.bluePlayer]) {
    select.innerHTML = "";
    for (const option of state.playerOptions) {
      const item = document.createElement("option");
      item.value = option.id;
      item.textContent = option.label;
      select.appendChild(item);
    }
  }
  updatePlayerLabels();
}

function updatePlayerLabels() {
  els.redPlayer.value = state.players[RED];
  els.bluePlayer.value = state.players[BLUE];
  els.redName.textContent = playerLabel(state.players[RED]);
  els.blueName.textContent = playerLabel(state.players[BLUE]);
  els.humanPanel.style.display = hasHumanPlayer() ? "block" : "none";
  els.moveEatMode.classList.toggle("active", state.humanActionMode === "move_eat");
  els.cascadeMode.classList.toggle("active", state.humanActionMode === "cascade");
}

function createCascadeButtons() {
  const wrap = document.createElement("div");
  wrap.className = "direction-buttons";
  wrap.id = "cascadeDirections";
  for (let di = 0; di < DIRS.length; di += 1) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = DIRS[di][2];
    button.addEventListener("click", () => handleCascadeDirection(di));
    wrap.appendChild(button);
  }
  els.humanPanel.appendChild(wrap);
  return wrap;
}

function updateCascadeButtons() {
  const wrap = document.getElementById("cascadeDirections") || createCascadeButtons();
  const game = state.game;
  const source = state.selectedHumanSource;
  const show = isHumanTurn() && game.phase === "play" && state.humanActionMode === "cascade" && source;
  wrap.style.display = show ? "grid" : "none";
  if (!show) return;

  const legal = new Set(game.legalActions());
  for (let di = 0; di < wrap.children.length; di += 1) {
    wrap.children[di].disabled = !legal.has(actionFromSource(source, "Cascade", di));
  }
}

function updateControls() {
  els.nextTurn.disabled = state.busy || !isAiTurn();
  els.newGame.disabled = state.busy;
  els.undoMove.disabled = state.busy || state.history.length === 0;
  els.redoMove.disabled = state.busy || state.redoStack.length === 0;
  els.runTen.disabled = state.busy || hasHumanPlayer();
  els.redPlayer.disabled = state.busy;
  els.bluePlayer.disabled = state.busy;
  updateAutoButton();
}

function updateAutoButton() {
  els.autoPlay.textContent = state.autoMode ? "Auto on" : "Auto off";
  els.autoPlay.classList.toggle("primary", state.autoMode);
}

function currentTeacherBudget() {
  return LEVEL_BUDGETS[Number(els.level.value)] ?? LEVEL_BUDGETS[3];
}

function updateLevelLabels() {
  const level = Number(els.level.value);
  const budget = currentTeacherBudget();
  els.levelLabel.textContent = level === 0 ? "instant" : `level ${level}`;
  els.budgetLabel.textContent = `${budget} sims`;
  if (state.teacherWorker) state.teacherWorker.postMessage({ type: "setBudget", sims: budget });
}

async function loadPlayerOptions() {
  try {
    const res = await fetch("/api/players");
    const data = await res.json();
    if (data.ok && Array.isArray(data.players)) {
      state.playerOptions = data.players;
      if (!state.playerOptions.some(item => item.id === state.players[RED])) {
        state.players[RED] = state.playerOptions.find(item => item.id.startsWith("agent:"))?.id || "human";
      }
      if (!state.playerOptions.some(item => item.id === state.players[BLUE])) {
        state.players[BLUE] = state.playerOptions.some(item => item.id === "teacher") ? "teacher" : "human";
      }
    }
  } catch (error) {
    showError(`Could not load player list: ${error.message}`);
  }
  renderPlayerOptions();
}

function sleep(ms) {
  return new Promise(resolve => window.setTimeout(resolve, ms));
}

function bindEvents() {
  els.redPlayer.addEventListener("change", () => {
    const previousPlayers = { ...state.players };
    state.players[RED] = els.redPlayer.value;
    switchPlayersAndContinue(previousPlayers);
  });

  els.bluePlayer.addEventListener("change", () => {
    const previousPlayers = { ...state.players };
    state.players[BLUE] = els.bluePlayer.value;
    switchPlayersAndContinue(previousPlayers);
  });

  els.moveEatMode.addEventListener("click", () => {
    state.humanActionMode = "move_eat";
    state.selectedHumanSource = null;
    render();
  });

  els.cascadeMode.addEventListener("click", () => {
    state.humanActionMode = "cascade";
    render();
  });

  els.level.addEventListener("input", updateLevelLabels);

  els.newGame.addEventListener("click", () => {
    state.autoMode = false;
    state.batchRemaining = 0;
    startGame();
  });

  els.nextTurn.addEventListener("click", () => {
    state.autoMode = false;
    state.batchRemaining = 0;
    updateAutoButton();
    playOneTurn();
  });

  els.undoMove.addEventListener("click", undoMove);
  els.redoMove.addEventListener("click", redoMove);

  els.autoPlay.addEventListener("click", () => {
    state.autoMode = !state.autoMode;
    state.batchRemaining = 0;
    updateAutoButton();
    if (state.autoMode) continueAuto(state.runId);
  });

  els.runTen.addEventListener("click", () => {
    if (hasHumanPlayer()) return;
    state.autoMode = true;
    state.batchRemaining = 10;
    updateAutoButton();
    startGame({ keepAuto: true, batch: true });
  });
}

async function main() {
  els.level.max = String(LEVEL_BUDGETS.length - 1);
  if (Number(els.level.value) > LEVEL_BUDGETS.length - 1) els.level.value = "3";
  bindEvents();
  updateLevelLabels();
  renderRecords();
  await loadPlayerOptions();
  await startGame();
}

main().catch(error => {
  showError(error.message);
});
