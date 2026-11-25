// Mascot settings. Change the character's habits here.

export const CONFIG = {
  // 'stand'  -> when clicked it stands on top of the card, feet and all
  // 'hover'  -> it floats just above the card (no feet)
  pose: 'stand',

  firstPeekDelay: 1400, // ms after the page loads before it first peeks out
  settleAfterScroll: 1000, // ms of stillness after scrolling before it moves to a new spot
  waveDelay: 700, // ms between peeking out and waving
  idleMoveMin: 11000, // while idle it moves to another spot every 11-18 seconds
  idleMoveMax: 18000,

  // What counts as a good hiding place (an element marked data-mascot-spot)
  spotMinWidth: 130,
  spotMinHeight: 96,
  viewportTopMargin: 130, // px kept free under the header
  viewportBottomMargin: 170,
};
