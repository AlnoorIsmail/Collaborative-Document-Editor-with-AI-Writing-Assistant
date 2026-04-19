import { a as PluginKey, c as TextSelection, i as Plugin } from "./dist-DF9O4ld3.js";
//#region node_modules/prosemirror-collab/dist/index.js
var Rebaseable = class {
	constructor(step, inverted, origin) {
		this.step = step;
		this.inverted = inverted;
		this.origin = origin;
	}
};
/**
Undo a given set of steps, apply a set of other steps, and then
redo them @internal
*/
function rebaseSteps(steps, over, transform) {
	for (let i = steps.length - 1; i >= 0; i--) transform.step(steps[i].inverted);
	for (let i = 0; i < over.length; i++) transform.step(over[i]);
	let result = [];
	for (let i = 0, mapFrom = steps.length; i < steps.length; i++) {
		let mapped = steps[i].step.map(transform.mapping.slice(mapFrom));
		mapFrom--;
		if (mapped && !transform.maybeStep(mapped).failed) {
			transform.mapping.setMirror(mapFrom, transform.steps.length - 1);
			result.push(new Rebaseable(mapped, mapped.invert(transform.docs[transform.docs.length - 1]), steps[i].origin));
		}
	}
	return result;
}
var CollabState = class {
	constructor(version, unconfirmed) {
		this.version = version;
		this.unconfirmed = unconfirmed;
	}
};
function unconfirmedFrom(transform) {
	let result = [];
	for (let i = 0; i < transform.steps.length; i++) result.push(new Rebaseable(transform.steps[i], transform.steps[i].invert(transform.docs[i]), transform));
	return result;
}
var collabKey = new PluginKey("collab");
/**
Creates a plugin that enables the collaborative editing framework
for the editor.
*/
function collab(config = {}) {
	let conf = {
		version: config.version || 0,
		clientID: config.clientID == null ? Math.floor(Math.random() * 4294967295) : config.clientID
	};
	return new Plugin({
		key: collabKey,
		state: {
			init: () => new CollabState(conf.version, []),
			apply(tr, collab) {
				let newState = tr.getMeta(collabKey);
				if (newState) return newState;
				if (tr.docChanged) return new CollabState(collab.version, collab.unconfirmed.concat(unconfirmedFrom(tr)));
				return collab;
			}
		},
		config: conf,
		historyPreserveItems: true
	});
}
/**
Create a transaction that represents a set of new steps received from
the authority. Applying this transaction moves the state forward to
adjust to the authority's view of the document.
*/
function receiveTransaction(state, steps, clientIDs, options = {}) {
	let collabState = collabKey.getState(state);
	let version = collabState.version + steps.length;
	let ourID = collabKey.get(state).spec.config.clientID;
	let ours = 0;
	while (ours < clientIDs.length && clientIDs[ours] == ourID) ++ours;
	let unconfirmed = collabState.unconfirmed.slice(ours);
	steps = ours ? steps.slice(ours) : steps;
	if (!steps.length) return state.tr.setMeta(collabKey, new CollabState(version, unconfirmed));
	let nUnconfirmed = unconfirmed.length;
	let tr = state.tr;
	if (nUnconfirmed) unconfirmed = rebaseSteps(unconfirmed, steps, tr);
	else {
		for (let i = 0; i < steps.length; i++) tr.step(steps[i]);
		unconfirmed = [];
	}
	let newCollabState = new CollabState(version, unconfirmed);
	if (options && options.mapSelectionBackward && state.selection instanceof TextSelection) {
		tr.setSelection(TextSelection.between(tr.doc.resolve(tr.mapping.map(state.selection.anchor, -1)), tr.doc.resolve(tr.mapping.map(state.selection.head, -1)), -1));
		tr.updated &= -2;
	}
	return tr.setMeta("rebased", nUnconfirmed).setMeta("addToHistory", false).setMeta(collabKey, newCollabState);
}
/**
Provides data describing the editor's unconfirmed steps, which need
to be sent to the central authority. Returns null when there is
nothing to send.

`origins` holds the _original_ transactions that produced each
steps. This can be useful for looking up time stamps and other
metadata for the steps, but note that the steps may have been
rebased, whereas the origin transactions are still the old,
unchanged objects.
*/
function sendableSteps(state) {
	let collabState = collabKey.getState(state);
	if (collabState.unconfirmed.length == 0) return null;
	return {
		version: collabState.version,
		steps: collabState.unconfirmed.map((s) => s.step),
		clientID: collabKey.get(state).spec.config.clientID,
		get origins() {
			return this._origins || (this._origins = collabState.unconfirmed.map((s) => s.origin));
		}
	};
}
/**
Get the version up to which the collab plugin has synced with the
central authority.
*/
function getVersion(state) {
	return collabKey.getState(state).version;
}
//#endregion
export { collab, getVersion, rebaseSteps, receiveTransaction, sendableSteps };

//# sourceMappingURL=@tiptap_pm_collab.js.map