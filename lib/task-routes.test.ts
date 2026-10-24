import { test } from 'node:test';
import assert from 'node:assert/strict';
import { findTask, taskHref, taskRoutes } from './task-routes';
import { findEntry } from './toc';

test('every task has a unique id, useful text, and existing chapter destination', () => {
  assert.ok(taskRoutes.length >= 10);
  assert.equal(new Set(taskRoutes.map((task) => task.id)).size, taskRoutes.length);
  for (const task of taskRoutes) {
    assert.ok(task.question.trim());
    assert.ok(task.description.trim());
    assert.ok(task.group.trim());
    for (const destination of [task, ...(task.related ? [task.related] : [])]) {
      assert.ok(findEntry(destination.slug), `${task.id}: missing chapter ${destination.slug}`);
      assert.match(destination.heading, /^[a-z0-9]+(?:-[a-z0-9]+)*$/);
      assert.equal(taskHref(destination), `/${destination.slug}#${destination.heading}`);
    }
    assert.equal(findTask(task.id), task);
  }
});

test('the cover task routes resolve to their intended sections', () => {
  assert.equal(taskHref(findTask('turnout-denominator')), '/ch01-estimands#what-was-turnout-in-2020');
  assert.equal(taskHref(findTask('choose-survey')), '/ch08-field-guide#six-surveys-at-a-glance');
  assert.equal(taskHref(findTask('nonresponse-assumption')), '/ch09-identification#missing-answers-turnout-as-a-set');
  assert.throws(() => findTask('missing'), /Unknown task route/);
});
