# SoundRadar roadmap

## Product direction: Your Radar

SoundRadar's release desk answers **"What came out?"** The next major feature should
answer **"What should I actually listen to?"**

Add a concise, song-level overview that selects the most promising new music from
both followed artists and carefully chosen new artists. This should be a finite,
explainable shortlist rather than another endless recommendation feed.

### Desired experience

- [x] Add a **Your Radar** overview that summarizes a large batch of new music into
      a small set of high-confidence song picks.
- [ ] Mix familiar and exploratory recommendations:
  - **Best Bets:** new songs from favorite or strongly preferred followed artists.
  - **Discoveries:** songs from new artists with strong connections to existing favorites.
  - **Deeper Listens:** a very small number of albums or EPs worth opening in full.
- [x] Show how much noise was removed, for example: "10 picks selected from 84 new
      tracks across 37 artists."
- [x] Offer three levels of detail:
  - **Quick glance:** approximately 5 songs.
  - **Your Radar:** approximately 10–15 songs.
  - **Everything new:** the existing complete release desk.
- [x] Keep recommendations separate from the release queue. Never automatically
      follow a new artist or add their full catalog.
- [x] Explain every selection with a short reason such as "Favorite artist," "New
      this week," or "Because you follow Artist A and Artist B."

### Recommendation signals

- [x] Let users explicitly mark followed artists as **Favorites**; make this the
      strongest familiar-artist signal.
- [x] Record the number of local-library tracks or albums associated with each artist
      as a softer affinity signal.
- [x] Treat releases marked **Downloaded** as positive preference evidence.
- [x] Add lightweight song feedback: **Love it**, **Not for me**, and **Already heard**.
- [x] Prioritize unseen songs released recently, especially standalone singles and
      notable tracks from new albums or EPs.
- [x] Limit each shortlist to one or two songs per artist so prolific artists cannot
      dominate it.
- [x] Collapse or suppress deluxe, remastered, clean, explicit, live, regional, and
      otherwise duplicated versions of the same song.
- [ ] Recommend a new artist only when there is a strong relationship to one or more
      preferred artists; boost candidates supported by multiple favorites.
- [x] Use provider-wide popularity only as a tie-breaker so the shortlist remains
      personal rather than generic.
- [x] Persist previously shown and dismissed items so refreshing the overview does not
      repeatedly surface the same unwanted songs.

### Required foundation

- [x] Add track-level storage linked to releases; the current model stores albums,
      EPs, and singles but not their individual songs.
- [x] Fetch track listings for newly detected releases without importing irrelevant
      historical catalogs into the main release desk.
- [x] Store recommendation score components and human-readable selection reasons so
      ranking behavior can be inspected and tested.
- [x] Add database and API regression tests for track deduplication, affinity scoring,
      diversity limits, feedback, and previously-seen suppression.

### Suggested delivery sequence

1. Add artist Favorites and retain local-library artist frequency during scans.
2. Add track storage and track fetching for newly detected releases.
3. Ship a familiar-artist-only Your Radar shortlist with reasons and diversity limits.
4. Add feedback learning and seen-item suppression.
5. Add high-confidence new-artist discoveries and Deeper Listens.

## Next

- [ ] Add an artist-resolution inbox with side-by-side Deezer candidates and batch confirmation.
- [ ] Cache Deezer search results briefly to reduce repeated lookups.
- [ ] Add optional notifications for newly discovered releases.
- [ ] Add an export/import command for settings, artists, and release statuses.

## Later

- [ ] Group deluxe, clean, explicit, and regional editions under one canonical release.
- [ ] Support additional metadata providers behind a provider interface.
- [ ] Add scheduled checks with a visible last-run history.
- [ ] Add end-to-end browser tests for search, filtering, and queue actions.
