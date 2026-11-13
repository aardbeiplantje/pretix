group "default" {
  targets = ["pretix"]
}
group "release" {
  targets = ["pretix"]
}
variable "DOCKER_REGISTRY" {
  default = "local"
}
variable "DOCKER_REPOSITORY" {
  default = "aardbeiplantje/pretix"
}
variable "DOCKER_TAG" {
  default = "latest"
}
target "pretix" {
  pull = true
  name = "pretix"
  matrix = {
    env = ["release"]
  }
  progress = ["plain", "tty"]
  tags = [
    "${DOCKER_REGISTRY}/${DOCKER_REPOSITORY}/pretix:${DOCKER_TAG}",
  ]
  buildkit = true
  attest = [
    "type=provenance,mode=max",
    "type=sbom",
  ]
  context = "."
  dockerfile = "Dockerfile"
  networks = ["host"]
  platforms = [
    "linux/amd64"
  ]
}
