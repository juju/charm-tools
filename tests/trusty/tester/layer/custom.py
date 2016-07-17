from charmtools.build.tactics import Tactic


class READMETactic(Tactic):
    """Example dynamically loaded tactic"""
    @classmethod
    def trigger(cls, entity, target, layer, combined_config):
        relpath = entity.relpath(layer.directory)
        return relpath.startswith("README")

    def __str__(self):
        return "READMETactic"

    def __call__(self):
        # Write out a fake readme for testing
        rel = self.entity.relpath(self.layer.directory)
        target = self.target.directory / rel
        target.write_text("dynamic tactics")
