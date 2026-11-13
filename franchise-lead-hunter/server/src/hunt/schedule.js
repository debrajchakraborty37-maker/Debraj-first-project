/** Is a hunt due in this UTC hour, given the saved schedule? Called hourly by cron or by Cloud Scheduler. */
export function isDue(schedule, hourUtc) {
  return schedule === 'hourly' || (schedule === 'every3h' && hourUtc % 3 === 0) || (schedule === 'daily' && hourUtc === 2);
}
