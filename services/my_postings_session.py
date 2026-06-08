"""FSM/session helpers for My Postings handlers."""

from services.my_postings_state import clamp_index, remove_post_key

MY_POSTINGS_IDS_KEY = "my_postings_ids"
MY_POSTINGS_INDEX_KEY = "my_postings_index"


async def get_my_postings_session(state):
    data = await state.get_data()
    return (
        data.get(MY_POSTINGS_IDS_KEY, []),
        data.get(MY_POSTINGS_INDEX_KEY, 0),
    )


async def set_my_postings_session(state, ids, index):
    await state.update_data(
        my_postings_ids=ids,
        my_postings_index=clamp_index(index, len(ids)),
    )


async def set_my_postings_index(state, index):
    ids, _ = await get_my_postings_session(state)
    new_index = clamp_index(index, len(ids))
    await state.update_data(my_postings_index=new_index)
    return new_index


async def move_my_postings_index(state, delta):
    ids, index = await get_my_postings_session(state)
    await state.update_data(my_postings_index=clamp_index(index + delta, len(ids)))


async def remove_my_postings_key(state, key):
    ids, index = await get_my_postings_session(state)
    new_ids, new_index = remove_post_key(ids, key, index)
    await set_my_postings_session(state, new_ids, new_index)
    return new_ids, new_index
