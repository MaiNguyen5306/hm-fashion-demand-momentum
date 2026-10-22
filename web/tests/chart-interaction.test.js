import test from 'node:test';
import assert from 'node:assert/strict';
import { nearestChartIndex, moveChartIndex } from '../src/chart-interaction.js';
test('pointer inspection uses the plot margins and scales with the displayed SVG',()=>{
  assert.equal(nearestChartIndex(70,0,960,101),0);
  assert.equal(nearestChartIndex(505,0,960,101),50);
  assert.equal(nearestChartIndex(940,0,960,101),100);
  assert.equal(nearestChartIndex(100+505/2,100,480,101),50);
  assert.equal(nearestChartIndex(-200,0,960,101),0);
  assert.equal(nearestChartIndex(2000,0,960,101),100);
  assert.equal(nearestChartIndex(400,0,960,1),0);
});
test('keyboard inspection steps between real observations and respects endpoints',()=>{
  assert.equal(moveChartIndex(null,'ArrowRight',10),1);
  assert.equal(moveChartIndex(0,'ArrowLeft',10),0);
  assert.equal(moveChartIndex(9,'ArrowRight',10),9);
  assert.equal(moveChartIndex(5,'Home',10),0);
  assert.equal(moveChartIndex(5,'End',10),9);
});
