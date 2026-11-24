export function reviewTransport(polish:boolean, forceModel:boolean, localOnly:boolean|undefined) {
  const usesModel=polish||forceModel||!localOnly
  return {usesModel,local_only:!usesModel}
}
