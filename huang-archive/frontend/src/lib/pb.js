import PocketBase from 'pocketbase'

const pb = new PocketBase(window.location.origin)
pb.autoCancellation(false)

export default pb
