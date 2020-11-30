/*
 * Copyright 2019 YugaByte, Inc. and Contributors
 *
 * Licensed under the Polyform Free Trial License 1.0.0 (the "License"); you
 * may not use this file except in compliance with the License. You
 * may obtain a copy of the License at
 *
 *     https://github.com/YugaByte/yugabyte-db/blob/master/licenses/POLYFORM-FREE-TRIAL-LICENSE-1.0.0.txt
 */

package com.yugabyte.yw.commissioner.tasks.subtasks;

import com.yugabyte.yw.common.NodeManager;
import com.yugabyte.yw.common.ShellProcessHandler;
import com.yugabyte.yw.forms.UniverseDefinitionTaskParams;
import com.yugabyte.yw.models.Universe;

import com.fasterxml.jackson.databind.JsonNode;

import play.libs.Json;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class PrecheckNode extends NodeTaskBase {

  public static final Logger LOG = LoggerFactory.getLogger(PrecheckNode.class);

  @Override
  public void run() {
    LOG.info("Running preflight checks for universe.");
    ShellProcessHandler.ShellResponse response = getNodeManager().nodeCommand(
        NodeManager.NodeCommandType.Precheck, taskParams());

    if (response.code == 0) {
      JsonNode responseJson = Json.parse(response.message);
      Universe.UniverseUpdater updater = new Universe.UniverseUpdater() {
        @Override
        public void run(Universe universe) {
          UniverseDefinitionTaskParams universeDetails = universe.getUniverseDetails();
          universeDetails.preflight_checks = responseJson;
          universe.setUniverseDetails(universeDetails);
            }
      };
      Universe.saveDetails(taskParams().universeUUID, updater);

      for (JsonNode node: responseJson) {
        if (!node.isBoolean() || !node.asBoolean()) {
          // If a check failed, change the return code so logShellResponse errors.
          response.code = 1;
          break;
        }
      }
    }
    logShellResponse(response);
  }
}
